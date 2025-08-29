import argparse
import logging
import os
import time
from datetime import datetime
from textwrap import dedent

import toml
import undetected_chromedriver as uc
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import track
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from . import utils
from .item import ScholarItem

FORMAT = "%(message)s"
logging.basicConfig(
    level=logging.INFO, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
)
console = Console()
log = logging.getLogger(__name__)


def log_failed_item(item_data, filename):
    try:
        with open(filename, "a") as f:
            toml.dump({"failed_item": item_data}, f)
        log.debug("Logged failed item to {filename}")
    except Exception as e:
        log.warning(f"Error logging failed item to {filename}: {e}")


def argument_parser():
    parser = argparse.ArgumentParser(
        description="Scrape scholarly articles and add them to Zotero."
    )
    parser.add_argument(
        "--query",
        default=os.getenv("QUERY"),
        type=str,
        help="The search query for scholarly articles. Default to the value from the `QUERY` environment variable.",
    )
    parser.add_argument(
        "--zotero-api-key",
        default=os.getenv("ZOTERO_API_KEY"),
        type=str,
        help="Zotero API key.",
    )
    parser.add_argument(
        "--zotero-library-id",
        default=os.getenv("ZOTERO_LIBRARY_ID"),
        type=str,
        help="Zotero library ID.",
    )
    parser.add_argument(
        "--zotero-library-type",
        default=os.getenv("ZOTERO_LIBRARY_TYPE"),
        type=str,
        help="Zotero library type.",
    )
    parser.add_argument(
        "--zotero-parent-collection-name",
        default=os.getenv("ZOTERO_PARENT_COLLECTION_NAME"),
        type=str,
        help="Zotero parent collection name.",
    )
    parser.add_argument(
        "--item-limit",
        default=500,
        type=int,
        help="Limit to the number of items that are scraped. Defaults to 500.",
    )
    return parser


def main(N=None):
    parser = argument_parser()
    args = parser.parse_args()
    if N is not None:
        args.item_limit = N

    zot = utils.setup_zotero_client(
        args.zotero_library_id, args.zotero_library_type, args.zotero_api_key
    )

    # Get or create parent collection
    parent_collection_id = None
    try:
        parent_collection_id = utils.get_or_create_collection(
            zot, args.zotero_parent_collection_name
        )
    except Exception:
        log.warning("Could not set up parent collection. Exiting.")
        return

    # Get or create date-stamped sub-collection
    today_date = datetime.now().strftime("%Y-%m-%d")
    date_collection_id = None
    try:
        date_collection_id = utils.get_or_create_collection(
            zot, today_date, parent_collection_id
        )
    except Exception:
        log.warning("Could not set up date-stamped sub-collection. Exiting.")
        return

    log.info(f"Searching for articles with query: '{args.query}'...")

    options = uc.ChromeOptions()
    browser = uc.Chrome(options=options)

    failed_items_data = []
    failed_log_filename = f"failed-items-{today_date}.toml"

    with browser:
        browser.get("https://scholar.google.com/")

        # Locate the search input field
        search_box = browser.find_element(By.NAME, "q")

        # Enter the search query
        search_box.send_keys(args.query)
        search_box.send_keys(Keys.RETURN)

    console.input(
        "[yellow bold]Press Enter when you have solved the reCAPTCHA to continue..."
    )

    items = []

    with browser:
        while len(items) < args.item_limit:
            try:
                titles = browser.find_elements(By.CSS_SELECTOR, "h3.gs_rt")
            except NoSuchElementException:
                time.sleep(0.1)

            while titles is None:
                try:
                    titles = browser.find_elements(By.CSS_SELECTOR, "h3.gs_rt")
                except NoSuchElementException:
                    time.sleep(0.1)

            for index, title in enumerate(titles, start=1):
                if len(items) >= args.item_limit:
                    break
                pub = title.text
                log.info(f'\nProcessing item {len(items) + 1}: "{pub}"')
                scholar_item = ScholarItem(title=pub, zot=zot)
                if scholar_item.retrieve_metadata():
                    item = scholar_item.to_zotero_item()
                    if item["DOI"]:
                        log.info(
                            dedent(
                                f"""
                            Found DOI {item["DOI"]}. Updated keys {
                                    ", ".join(
                                        [
                                            k
                                            for k in item.keys()
                                            if k != "DOI"
                                            and (
                                                item[k] != []
                                                and item[k] != ""
                                                and item[k] != {}
                                            )
                                        ]
                                    )
                                }\
                            """
                            )
                        )
                        item["collections"] = [date_collection_id]
                        item["title"] = (
                            str(len(items) + 1).zfill(len(str(args.item_limit)))
                            + " - "
                            + item["title"]
                        )
                        items.append(item)
                    else:
                        failed_items_data.append(item)
                        log.warning(f"No DOI found. Skipping {index}...")
                else:
                    failed_items_data.append(scholar_item.zotero_item)
                    log.warning(f"No metadata found. Skipping {index}...")
            if len(items) >= args.item_limit:
                break
            log.info("Navigating to next page...\n ")

            # TODO: Sometimes the next button is not present on the page because the page has a different size. It
            # should hold the index of the page and instead then search for the next index which is always on the page. <28-08-25>
            next_button = None
            try:
                next_button = browser.find_element(By.LINK_TEXT, "Next")
            except NoSuchElementException:
                time.sleep(0.1)
            while next_button is None:
                try:
                    next_button = browser.find_element(By.LINK_TEXT, "Next")
                except NoSuchElementException:
                    time.sleep(0.1)

            next_button.click()

    browser.quit()

    return items

    response = None
    try:
        for items_50 in track(
            [items[i : i + 50] for i in range(0, len(items), 50)],
            description="Adding items to Zotero...",
        ):
            response = zot.create_items(items_50)
            if len(response["failed"]):
                log.warning(f"Some items failed to be added: {response['failed']}")
    except Exception as e:
        log.warning(f"Error adding items to Zotero: {e}")
        return

    log.info("Adding items to the date collection...")
    for _, item in track(
        response["successful"].items(), description="Adding items to collection..."
    ):
        zot.addto_collection(date_collection_id, item)

    log.info(
        dedent(f"""
                    --- Summary ---
                    Added {len(items)} to collection {date_collection_id} as a subcollection of {parent_collection_id}
                    """)
    )

    if failed_items_data:
        log.warning(
            f"Failed to add {len(failed_items_data)} articles. Details logged to {failed_log_filename}"
        )
        log_failed_item(failed_items_data, failed_log_filename)
    else:
        log.info("No articles failed to be added.")


if __name__ == "__main__":
    main()
