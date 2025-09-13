import logging
import re
import tempfile
from pathlib import Path
from typing import Optional
from urllib import request

import humanize
import pathvalidate
from bs4 import BeautifulSoup
from pyzotero.zotero import Zotero
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Possible item types available in Zotero. Can be retrieved using the Zotero API using `zot.item_types()`.
ZOTERO_ITEM_TYPES = [
    "artwork",
    "audioRecording",
    "bill",
    "blogPost",
    "book",
    "bookSection",
    "case",
    "conferencePaper",
    "dataset",
    "dictionaryEntry",
    "document",
    "email",
    "encyclopediaArticle",
    "film",
    "forumPost",
    "hearing",
    "instantMessage",
    "interview",
    "journalArticle",
    "letter",
    "magazineArticle",
    "manuscript",
    "map",
    "newspaperArticle",
    "note",
    "patent",
    "podcast",
    "preprint",
    "presentation",
    "radioBroadcast",
    "report",
    "computerProgram",
    "standard",
    "statute",
    "tvBroadcast",
    "thesis",
    "videoRecording",
    "webpage",
]


class ScholarItem:
    def __init__(
        self,
        title: str,
        zot: Optional[Zotero] = None,
    ):
        """
        Initialize a ScholarItem with a title and optional Zotero library.

        :param title: Title of the Google Scholar item
        :param zot: Zotero library instance
        :param webdriver: WebDriver instance
        """
        self.title = title
        self._set_default_attributes()
        self._strip_title()
        self.zot = zot
        self.item_type = "book" if self.is_book else "journalArticle"  # Default type
        self.zotero_item = zot.item_template(self.item_type) if zot else None
        from .enrichers import CrossrefEnricher

        self.enrichers = [CrossrefEnricher()]
        self.failed_enrichers = []

    def _set_default_attributes(self):
        self.abstract = None
        self.authors = None

        self.url = None

        self.logger = logging.getLogger(__name__)

        self.pdf_path = None
        self.attachments = []

        self.zot_id = None

        self.webdriver = None
        self.webelement = None
        self.timeout = 10

        self.is_book = False
        self.is_pdf = False
        self.is_html = False
        self.metadata_tags = []

        self.alternate_pdf_sources = []
        self.alternates = []

    def _strip_title(self):
        """
        Remove metadata like "[book]", "[pdf]" from the title and set corresponding attributes.
        """
        # Regex to find patterns like [word], [word-word], [word_word]
        metadata_pattern = re.compile(r"\[([a-zA-Z0-9_-]+)\]")
        found_metadata = metadata_pattern.findall(self.title)

        for tag in found_metadata:
            if tag.lower() == "book":
                self.is_book = True
            elif tag.lower() == "pdf":
                self.is_pdf = True
            elif tag.lower() == "html":
                self.is_html = True
            else:
                self.metadata_tags.append(tag)

        # Remove the metadata tags from the title
        self.title = metadata_pattern.sub("", self.title).strip()

    def with_alternate_source(self, url: str):
        self.alternate_pdf_sources.append(url)
        return self

    def with_zotero(self, zot: Zotero):
        self.zot = zot
        return self

    def with_zot_id(self, zot_id: str):
        self.zot_id = zot_id
        return self

    def with_logger(self, logger: logging.Logger):
        self.logger = logger
        for e in self.enrichers:
            e.with_logger(logger)
        return self

    def with_url(self, url: str):
        self.url = url
        return self

    def with_driver_and_elem(self, webdriver: WebDriver, element):
        self.webdriver = webdriver
        self.webelement = element
        return self

    def with_timeout(self, timeout: int):
        self.timeout = timeout
        return self

    @classmethod
    def from_div(
        cls,
        div: str,
    ):
        div_soup = BeautifulSoup(div, "html.parser")

        title_h3 = div_soup.find("h3", class_="gs_rt")
        if title_h3 is None:
            raise ValueError("Could not find title")

        title = title_h3.text
        url_anchor = title_h3.find("a")
        url = url_anchor["href"] if url_anchor else None

        # Extract abstract if available
        abstract_div = div_soup.find("div", class_="gs_rs")
        abstract = abstract_div.text if abstract_div else None

        # Extract authors if available
        authors_div = div_soup.find("div", class_="gs_a")
        authors = []
        if authors_div:
            authors = [
                a.strip().strip("…") for a in authors_div.text.split("-")[0].split(",")
            ]
        else:
            authors = None

        item = cls(title)
        if url:
            item.with_url(url)
        item.abstract = abstract
        item.authors = authors

        try:
            alternate_source = div_soup.select_one("div.gs_ggs.gs_fl")
            if alternate_source:
                alternate_anchor = alternate_source.find_next("a")
                if alternate_anchor:
                    metadata_pattern = re.compile(r"\[([a-zA-Z0-9_-]+)\]")
                    found_metadata = [
                        t.lower()
                        for t in metadata_pattern.findall(alternate_anchor.text)
                    ]
                    if "pdf" in found_metadata and alternate_anchor:
                        link = alternate_anchor["href"]
                        item.with_alternate_source(link)
                        item.logger.debug(
                            f'Alternate source for "{item.title}" PDF found: {link}'
                        )
                    else:
                        item.logger.debug(
                            f'Alternate source for "{item.title}" is not a PDF source.'
                        )
        except NoSuchElementException:
            item.logger.debug(
                f'Could not find the alternate source for the item: "{item.title}"'
            )
        return item

    def download_pdf(self, max_size=None) -> Optional[Path]:
        sources = []
        for s in [self] + self.alternates:
            sources.extend(s.alternate_pdf_sources)
            if s.is_pdf:
                sources.append(s.url)
        self.attachment_dir = Path(tempfile.mkdtemp())
        self.pdf_name = pathvalidate.sanitize_filename(
            f"{self.title.replace(' ', '_')}.pdf", platform="auto"
        )
        for source in sources:
            try:
                if max_size:
                    site = request.urlopen(source)
                    size = int(site.getheader("Content-Length", "0"))
                    if size > max_size:
                        self.logger.warning(
                            f"Maximum size of the PDF exceeded. PDF size {humanize.naturalsize(size)} > {humanize.naturalsize(max_size)}. Skipping download..."
                        )
                        continue
                pdf = request.urlretrieve(source, self.attachment_dir / self.pdf_name)
                self.logger.info(
                    f'Downloaded PDF to "{self.attachment_dir / self.pdf_name}" from {source}'
                )
                self.pdf_path = pdf[0]
                self.attachments.append(self.pdf_path)
                return self.pdf_path
            except Exception as e:
                self.logger.debug(f"Error downloading PDF: {e}")

        return False

    # TODO: Update the alternatives with `all versions` part of the div <04-09-25>

    def retrieve_metadata(self, enrichers=None):
        """
        Retrieve metadata from specified enrichers.

        :param enrichers: List of enrichers to try. If None, tries all available enrichers.
        :return: True if metadata was successfully retrieved, False otherwise
        """
        enrichers = enrichers or self.enrichers
        self._setup_zotero_template()
        for enricher in enrichers:
            enriched = enricher.enrich(self.title, self.abstract, self.authors)
            if enriched:
                self.apply_enriched_data(enriched)
                return True
            else:
                self.failed_enrichers.append(enricher.__class__.__name__)

        return False

    def apply_enriched_data(self, enriched: dict, update_title=False):
        """
        Apply enriched data to the Zotero item, filtering by field requirements.

        :param enriched: Dict of enriched metadata
        """
        if enriched.get("itemType", self.item_type) != self.item_type:
            if enriched["itemType"] not in ZOTERO_ITEM_TYPES:
                self.logger.warning(f'Unknown item type: "{enriched["itemType"]}"')
            else:
                self.item_type = enriched["itemType"]
            # FIX: Here we are applying for all potential enrichers instead and mutating instead of checking, which
            # enricher is the best <07-09-25>
            self._setup_zotero_template()
        for key, value in enriched.items():
            if key == "itemType":
                continue
            if not update_title and key == "title":
                self.zotero_item["title"] = self.title
            elif key in self.zotero_item.keys():
                self.zotero_item[key] = value
            else:
                self.logger.debug(
                    f"Ignoring enriched metadata field '{key}' for item type '{self.item_type}'"
                )

    # FIX: Alternates only located on the first page <07-09-25>
    def get_alternates(self) -> bool:
        if not self.webdriver or not self.webelement:
            return False

        webdriver = self.webdriver
        webelement = self.webelement
        timeout = self.timeout

        alternates_elements = webelement.find_elements(By.CSS_SELECTOR, "a.gs_nph")
        alternates_elements = list(
            filter(lambda e: re.match("All .*", e.text), alternates_elements)
        )
        if not alternates_elements:
            return False
        alternate_anchor = alternates_elements[0]

        action = ActionChains(webdriver)
        action.move_to_element(alternate_anchor).click().perform()

        try:
            divs = WebDriverWait(webdriver, timeout).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "div.gs_r.gs_or.gs_scl")
                )
            )
        except Exception as e:
            self.logger.error(
                f'Getting alternates failed for item "{self.title}" with error:\n{e}'
            )

            webdriver.execute_script("window.history.go(-1)")
            return False

        for div in divs:
            div_html = div.get_attribute("outerHTML")
            assert div_html
            self.alternates.append(ScholarItem.from_div(div_html))

        webdriver.execute_script("window.history.go(-1)")

        return True

    # FIX: Alternates are currently not cached, which can be an issue <12-09-25>
    def to_dict(self) -> dict:
        d = dict()
        for serializable in [
            "abstract",
            "alternate_pdf_sources",
            "authors",
            "is_book",
            "is_html",
            "is_pdf",
            "item_type",
            "metadata_tags",
            "timeout",
            "title",
            "url",
            "zot_id",
            "zotero_item",
        ]:
            d[serializable] = getattr(self, serializable)

        if self.attachments:
            d["attachments"] = [str(a) for a in self.attachments]

        return d

    @classmethod
    def from_dict(cls, d: dict):
        assert "title" in d.keys()
        item = cls(d["title"])
        for k in [
            "abstract",
            "alternate_pdf_sources",
            "authors",
            "is_book",
            "is_html",
            "is_pdf",
            "item_type",
            "metadata_tags",
            "timeout",
            "url",
            "zot_id",
            "zotero_item",
        ]:
            if k in d.keys():
                setattr(item, k, d[k])

        if "attachments" in d.keys():
            setattr(item, "attachments", [Path(a) for a in d["attachments"]])

        return item

    def _setup_zotero_template(self):
        assert self.zot
        assert self.item_type in ZOTERO_ITEM_TYPES
        self.zotero_item = self.zot.item_template(self.item_type)
        if not self.zotero_item:
            self.logger.error(
                f"Could not find Zotero template for item type '{self.item_type}'"
            )
            self.zotero_item = {}
        if "title" in self.zotero_item.keys():
            self.zotero_item["title"] = self.title
        if "abstractNote" in self.zotero_item.keys():
            self.zotero_item["abstractNote"] = self.abstract
        if "creators" in self.zotero_item.keys() and self.authors:
            self.zotero_item["creators"] = [
                {
                    "creatorType": "author",
                    "firstName": list_get(a.split(" "), 0, ""),
                    "lastName": list_get(a.split(" "), 1, ""),
                }
                for a in self.authors
            ]

    def to_zotero_item(self) -> dict:
        """
        Return the Zotero item representation.

        :return: Dictionary representing the Zotero item
        """
        return self.zotero_item

    def upload_attachments(self) -> Optional[dict]:
        if not self.zot or not self.zot_id:
            return None
        return self.zot.attachment_simple(
            [str(i.absolute()) for i in self.attachments], self.zot_id
        )


def list_get(li, idx, default=None):
    try:
        return li[idx]
    except IndexError:
        return default
