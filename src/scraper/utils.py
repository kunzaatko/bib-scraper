import logging
import os

from pyzotero import zotero
from rich.console import Console
from rich.table import Table
from rich.text import Text


def get_or_create_collection(
    zot,
    collection_name,
    parent_collection_id=None,
    logger=logging.getLogger(__name__),
):
    """
    Get or create the collection in Zotero
    """
    collections = zot.collections()

    # Filter collections by name and parent (if parent_collection_id is provided)
    target_collection = None
    for collection in collections:
        if collection["data"]["name"] == collection_name:
            if parent_collection_id is None and not collection["data"].get(
                "parentCollection"
            ):
                target_collection = collection
                break
            elif (
                parent_collection_id is not None
                and collection["data"].get("parentCollection") == parent_collection_id
            ):
                target_collection = collection
                break

    if target_collection:
        logger.info(f'Found existing collection: "{collection_name}"')
        return target_collection["data"]["key"]
    else:
        logger.info(f'Creating new collection: "{collection_name}"')
        new_collection_data = {"name": collection_name}
        if parent_collection_id:
            new_collection_data["parentCollection"] = parent_collection_id

        try:
            new_collection = zot.create_collections([new_collection_data])
            if (
                new_collection
                and "success" in new_collection
                and new_collection["success"]
            ):
                # The key is usually the value of the first (and only) item in the success dict
                return list(new_collection["success"].values())[0]
            else:
                raise Exception(f'Failed to create collection: "{collection_name}"')
        except Exception as e:
            logger.error(f'Error creating collection "{collection_name}": {e}')
            raise


def setup_zotero_client(libid=None, libtype=None, apikey=None):
    if libid is None:
        libid = os.getenv("ZOTERO_LIBRARY_ID")
    if libtype is None:
        libtype = os.getenv("ZOTERO_LIBRARY_TYPE")
    if apikey is None:
        apikey = os.getenv("ZOTERO_API_KEY")
    return zotero.Zotero(libid, libtype, apikey)


def log_table(table: Table):
    """Generate an ASCII formatted presentation of a Rich table
    Eliminates any column styling
    """
    console = Console()
    with console.capture() as capture:
        console.print(table)
    return Text.from_ansi(capture.get()).markup
