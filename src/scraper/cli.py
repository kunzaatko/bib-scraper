import argparse
import logging
import logging.config
import os
from datetime import datetime
from textwrap import dedent

import toml
import undetected_chromedriver as uc
from rich.console import Console
from rich.progress import Progress, track
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from . import utils
from .item import ScholarItem

DEFAULT_LOGGING = {
    "version": 1,
    "formatters": {
        "onlymessage": {
            "format": "%(message)s",
            "datefmt": "%H:%M",
        },
        "standard": {
            "format": "%(asctime)s %(levelname)s: %(message)s",
            "datefmt": "%Y-%m-%d - %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "rich.logging.RichHandler",
            "formatter": "onlymessage",
            "level": "DEBUG",
        },
        "file": {
            "class": "logging.FileHandler",
            "formatter": "standard",
            "level": "DEBUG",
            "filename": f"scraper_{datetime.now().strftime('%Y-%m-%d')}.log",
            "mode": "w",
        },
    },
    "loggers": {
        __name__: {
            "level": "INFO",
            "handlers": ["console", "file"],
            "propagate": False,
        },
    },
}
FORMAT = "%(message)s"
logging.config.dictConfig(DEFAULT_LOGGING)
log = logging.getLogger(__name__)
console = Console()


def log_failed_item(item_data, filename):
    try:
        with open(filename, "a") as f:
            toml.dump({"failed_item": item_data}, f)
        log.debug("Logged failed item to {filename}")
    except Exception as e:
        log.warning(f'Error logging failed item to "{filename}": {e}')


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
    parser.add_argument(
        "--timeout",
        default=10,
        type=int,
        help="Maximum timeout (in seconds) of the Chrome driver used for waiting for loading elements. Defaults to 10 seconds.",
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
            zot, args.zotero_parent_collection_name, logger=log
        )
    except Exception:
        log.warning("Could not set up parent collection. Exiting.")
        return 2

    # Get or create date-stamped sub-collection
    today_date = datetime.now().strftime("%Y-%m-%d")
    date_collection_id = None
    try:
        date_collection_id = utils.get_or_create_collection(
            zot, today_date, parent_collection_id, logger=log
        )
    except Exception:
        log.warning("Could not set up date-stamped sub-collection. Exiting.")
        return 2

    log.info(f"Searching for articles with query: '{args.query}'...")

    options = uc.ChromeOptions()
    # TODO: Recognize the chrome version that is used with `google-chrome --version` <04-09-25>
    browser = uc.Chrome(version_main=139, options=options)

    identify_failed_items = []
    identify_failed_logfile = f"failed-to-identify-items-{today_date}.toml"

    with browser:
        browser.get("https://scholar.google.com/")
        try:
            search_box = WebDriverWait(browser, args.timeout).until(
                EC.presence_of_element_located((By.NAME, "q"))
            )
        except TimeoutException:
            log.error("Timed out waiting for page to load. Exiting.")
            return 1

        # Enter the search query
        search_box.send_keys(args.query)
        search_box.send_keys(Keys.RETURN)

        # If a captcha appears then no items are found on the page and the user is prompted to solve it
        try:
            WebDriverWait(browser, args.timeout).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "div.gs_r.gs_or.gs_scl")
                )
            )
        except TimeoutException:
            console.input(
                "[yellow bold]Press Enter when you have solved the reCAPTCHA to continue..."
            )

    items = []

    with browser:
        progress = Progress()
        progress.start()
        items_task = progress.add_task("[yellow]Scraping...", total=args.item_limit)
        while len(items) < args.item_limit:
            try:
                divs = WebDriverWait(browser, args.timeout).until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "div.gs_r.gs_or.gs_scl")
                    )
                )
            except TimeoutException:
                log.error("Timed out waiting for page to load. Exiting.")
                return 1

            for div in divs:
                if len(items) >= args.item_limit:
                    break

                div_html = div.get_attribute("outerHTML")
                assert div_html

                scholar_item = ScholarItem.from_div(div_html)
                scholar_item.with_zotero(zot)

                log.info(f'Processing item {len(items) + 1}: "{scholar_item.title}"...')

                if scholar_item.retrieve_metadata():
                    item = scholar_item.to_zotero_item()
                    if item["DOI"]:
                        log.info(
                            dedent(
                                f"""\
                            Found [magenta]DOI[/magenta] "{item["DOI"]}". Updated keys {
                                    ", ".join(
                                        [
                                            f"[magenta]{k}[/magenta]"
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
                            ),
                            extra={"markup": True},
                        )
                        item["collections"] = [date_collection_id]
                        item["title"] = (
                            str(len(items) + 1).zfill(len(str(args.item_limit)))
                            + " - "
                            + item["title"]
                        )
                        items.append(item)
                        progress.update(items_task, advance=1)
                    else:
                        identify_failed_items.append(item)
                        log.warning(f"No DOI found. Skipping {len(items) + 1}...")
                else:
                    identify_failed_items.append(scholar_item.zotero_item)
                    log.warning(f"No metadata found. Skipping {len(items) + 1}...")
            if len(items) >= args.item_limit:
                break
            log.info("Navigating to next page...")

            # TODO: Sometimes the next button is not present on the page because the page has a different size. It
            # should hold the index of the page and instead then search for the next index which is always on the page. <28-08-25>

            try:
                next_button = WebDriverWait(browser, args.timeout).until(
                    EC.presence_of_element_located((By.LINK_TEXT, "Next"))
                )
            except TimeoutException:
                log.error("Timed out waiting for page to load. Exiting.")
                return 1

            next_button.click()
        progress.stop()
    browser.quit()

    added_items = []
    create_failed_items = []
    create_failed_logfile = f"failed-to-create-items-{today_date}.toml"
    try:
        for items_50 in track(
            [items[i : i + 50] for i in range(0, len(items), 50)],
            description="Adding items to Zotero...",
        ):
            response = zot.create_items(items_50)
            if len(response["failed"]):
                log.warning(f"Some items failed to be added: {response['failed']}")
                create_failed_items.extend(response["failed"])
            added_items.extend(response["successful"].items())
    except Exception as e:
        log.warning(f"Error adding items to Zotero: {e}")
        return 3

    # NOTE: Effectively once the items are uploaded, this should not fail <04-09-25>
    log.info("Adding items to the date collection...")
    for _, item in track(
        added_items,
        description="Adding items to collection...",
    ):
        zot.addto_collection(date_collection_id, item)

    log.info(
        f'[bold]Summary:[/bold] Added {len(added_items)} items to collection "{date_collection_id}" as a subcollection of "{parent_collection_id}"',
        extra={"markup": True},
    )

    if create_failed_items:
        log.warning(
            f'[bold]Summary:[/bold] Failed to create {len(create_failed_items)} items. Failed items have been logged to "{create_failed_logfile}".',
            extra={"markup": True},
        )
        for item in create_failed_items:
            log_failed_item(item, create_failed_logfile)

    if identify_failed_items:
        log.warning(
            f'[bold]Summary:[/bold] Failed to identify {len(identify_failed_items)} items. Failed items have been logged to "{identify_failed_logfile}".',
            extra={"markup": True},
        )
        for item in identify_failed_items:
            log_failed_item(item, identify_failed_logfile)


if __name__ == "__main__":
    main()
