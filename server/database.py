import weaviate
import os
import logging
import re
import traceback

logging.basicConfig(level=logging.DEBUG)

INDEX_NAME = "VNTANA"

SCHEMA = {
    "class": INDEX_NAME,
    "properties": [
        {"name": "text", "dataType": ["text"]},
        {"name": "document_id", "dataType": ["string"]},
    ],
}

def _is_wcs_domain(url: str) -> bool:
    """
    Check if the given URL ends with ".weaviate.network" or ".weaviate.network/".
    """
    pattern = r"\.(weaviate\.cloud|weaviate\.network)(/)?$"
    return bool(re.search(pattern, url))

def _build_auth_credentials():
    url = os.environ.get("WEAVIATE_URL", "https://qkkaupkrrpgbpwbekvzvw.gcp-c.weaviate.cloud")

    if _is_wcs_domain(url):
        api_key = os.environ.get("WEAVIATE_API_KEY")
        if api_key is not None:
            return weaviate.auth.AuthApiKey(api_key=api_key)
        else:
            raise ValueError("WEAVIATE_API_KEY environment variable is not set")
    else:
        return None

def get_client():
    """
    Get a client to the Weaviate server
    """
    host = os.environ.get("WEAVIATE_HOST", "https://qkkaupkrrpgbpwbekvzvw.gcp-c.weaviate.cloud")
    auth_credentials = _build_auth_credentials()
    return weaviate.Client(host, auth_client_secret=auth_credentials)


def init_db():
    # Retrieve keys from environment variables
    weaviate_url = os.getenv("WEAVIATE_URL")
    weaviate_api_key = os.getenv("WEAVIATE_API_KEY")
    openai_api_key = os.getenv("OPEN_AI_API_KEY")

    client = weaviate.Client(
        url=weaviate_url,
        auth_client_secret=weaviate.AuthApiKey(api_key=weaviate_api_key),
        additional_headers={"X-OpenAI-Api-Key": openai_api_key},
    )

    logging.info("Connected to Weaviate")

    try:
        # Print the entire schema
        schema = client.schema.get()
        print(f"Current schema: {schema}")

        # Check if the schema contains the class
        if not client.schema.contains("VNTANA"):
            logging.info("VNTANA class not found, creating...")
            # If not, create the class
            class_obj = {
                "class": "VNTANA",
                "properties": [
                    {
                        "dataType": ["text"],
                        "name": "title",
                    },
                    {
                        "dataType": ["text"],
                        "name": "body",
                    },
                ],
            }
            client.schema.create_class(class_obj)
            logging.info("VNTANA class created")
    except Exception as e:
        print(f"Error initializing database: {e}")
        logging.error(f"Error initializing database: {e}")
        logging.error(traceback.format_exc())
