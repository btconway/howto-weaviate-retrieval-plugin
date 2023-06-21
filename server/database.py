import weaviate
import os
import logging
import re

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
    """
    Create the schema for the database if it doesn't exist yet
    """
    client = get_client()
    class_name = SCHEMA["class"]

    try:
        client.schema.get_class(class_name)
        logging.debug(f"Schema for {class_name} already exists")
        logging.debug("Skipping schema creation")
    except weaviate.exceptions.ClassNotFound:
        logging.debug("Creating schema")
        client.schema.create_class(SCHEMA)

