from typing import List
from fastapi import Depends, FastAPI, HTTPException
from contextlib import asynccontextmanager

from .database import get_client, init_db, INDEX_NAME
from .embedding import get_embedding
from pydantic import BaseModel

from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import openai
import weaviate

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer_scheme = HTTPBearer()
BEARER_TOKEN = os.environ.get("BEARER_TOKEN")

openai.api_key = os.environ.get("OPENAI_API_KEY")

def get_concepts(query_text):
    """
    Use OpenAI's chat API to generate a summary of concepts from the query text.
    """
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k-0613",
        messages=[
            {
                "role": "system",
                "content": "You are an AI Assistant for VNTANA. Your only task is to provide useful queries for semantic search in my weaviate vector database. You are only concerned with the semantics of the user input. Your first task is to read the user input and determine what the VNTANA employee needs. Then, create a list of concepts to query based on the summary separated by commas. Finally, check your work against the below description of VNTANA and its products to make sure your query is relevant and return a query that follows the exact format below. Each concept to query is separated by a comma. This is all that you should return to me. I do not want to see the summary in your response at all."
            },
            {
                "role": "user",
                "content": f"Here is the user input: {query_text}. Return on the concepts to query in separated by a comma as per your assistant instructions. Do not provide any other text including, but not limited to 'concepts to query' or 'relevant concepts' or 'relevant queries'. Do not use any quotations when separating the concepts to query."
            }
        ]
    )

    # Extract the assistant's reply
    assistant_reply = response['choices'][0]['message']['content']

    # Split the reply into a list of concepts
    concepts = assistant_reply.split(', ')

    return concepts


def validate_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if credentials.scheme != "Bearer" or credentials.credentials != BEARER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return credentials


class Document(BaseModel):
    text: str
    document_id: str


class Query(BaseModel):
    text: str
    limit: int = 4


class QueryResult(BaseModel):
    document: Document
    score: float


class DeleteRequest(BaseModel):
    document_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.mount("/.well-known", StaticFiles(directory=".well-known"), name="static")

# for localhost deployment
if os.getenv("ENV", "dev") == "dev":
    origins = [
        f"http://localhost:8000",
        "https://chat.openai.com",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def get_weaviate_client():
    """
    Get a client to the Weaviate server
    """
    # Retrieve keys from environment variables
    weaviate_url = os.getenv("WEAVIATE_URL")
    weaviate_api_key = os.getenv("WEAVIATE_API_KEY")
    openai_api_key = os.getenv("OPEN_AI_API_KEY")

    client = weaviate.Client(
        url=weaviate_url,
        auth_client_secret=weaviate.AuthApiKey(api_key=weaviate_api_key),
        additional_headers={"X-OpenAI-Api-Key": openai_api_key},
    )
    yield client



@app.get("/")
def read_root():
    """
    Say hello to the world
    """
    return {"Hello": "World"}


@app.post("/upsert")
def upsert(
    doc: Document,
    client=Depends(get_weaviate_client),
    token: HTTPAuthorizationCredentials = Depends(validate_token),
):
    """
    Insert a document into weaviate
    """
    with client.batch as batch:
        batch.add_data_object(
            data_object=doc.dict(),
            class_name=INDEX_NAME,
            vector=get_embedding(doc.text),
        )

    return {"status": "ok"}


@app.post("/query", response_model=List[QueryResult])
def query(
    query: Query,
    client=Depends(get_weaviate_client),
    token: HTTPAuthorizationCredentials = Depends(validate_token),
) -> List[Document]:
    """
    Query weaviate for documents
    """
    # Get a list of concepts from the query text
    concepts = get_concepts(query.text)

    results = (
        client.query.get(INDEX_NAME, ["text"])
        .with_near_text({"concepts": concepts})
        .with_limit(query.limit)
        .with_additional("certainty")
        .do()
    )

    if 'data' not in results or 'Get' not in results['data'] or INDEX_NAME not in results['data']['Get']:
        print(f"Unexpected results from Weaviate query: {results}")
        raise HTTPException(status_code=500, detail="Unexpected results from Weaviate query")

    docs = results["data"]["Get"].get(INDEX_NAME, [])

    return [
        QueryResult(
            document={"text": doc["text"], "document_id": doc.get("document_id", "default_value")},
            score=doc["_additional"]["certainty"],
        )
        for doc in docs if "text" in doc
    ]


@app.post("/delete")
def delete(
    delete_request: DeleteRequest,
    client=Depends(get_weaviate_client),
    token: HTTPAuthorizationCredentials = Depends(validate_token),
):
    """
    Delete a document from weaviate
    """
    result = client.batch.delete_objects(
        class_name=INDEX_NAME,
        where={
            "operator": "Equal",
            "path": ["document_id"],
            "valueString": delete_request.document_id,
        },
    )

    if result["results"]["successful"] == 1:
        return {"status": "ok"}
    else:
        return {"status": "not found"}
