import requests


class ScholarItem:
    ITEM_TYPE_MAPPING = {
        "journal-article": "journalArticle",
        "book": "book",
        "book-chapter": "bookSection",
        "conference-paper": "conferencePaper",
        "thesis": "thesis",
        "report": "report",
        "webpage": "webpage",
        "manuscript": "manuscript",
        "patent": "patent",
        "dataset": "dataset",
        "software": "computerProgram",
        "map": "map",
        "entry-dictionary": "dictionaryEntry",
        "entry-encyclopedia": "encyclopediaArticle",
    }

    CROSSREF_URL = "https://api.crossref.org/works"

    def __init__(self, title=None, zot=None):
        """
        Initialize a ScholarItem with a title and optional Zotero library.

        :param title: Title of the Google Scholar item
        :param zot: Zotero library instance
        """
        self.title = title
        self.zot = zot
        self.item_type = "journalArticle"  # Default type
        self.zotero_item = zot.item_template(self.item_type) if zot else {}
        self.metadata_sources = {
            "crossref": self._update_from_crossref,
        }
        self.failed_metadata_sources = []

    def _update_from_crossref(self):
        """
        Update item metadata and type using CrossRef API.

        :return: True if metadata was successfully updated, False otherwise
        """
        if not self.title:
            return False

        params = {"query.title": self.title, "rows": 1}
        try:
            response = requests.get(self.CROSSREF_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data["message"]["items"]:
                match = data["message"]["items"][0]

                # Determine item type based on CrossRef type
                crossref_type = match.get("type", "journal-article")
                self.item_type = self.ITEM_TYPE_MAPPING.get(
                    crossref_type, "journalArticle"
                )

                # Recreate Zotero item template with detected type
                if self.zot:
                    self.zotero_item = self.zot.item_template(self.item_type)

                # Metadata update logic
                self._safe_update(match, "title", lambda x: x[0], "title")
                self._safe_update(match, "author", self._process_authors, "creators")
                self._safe_update(match, "abstract", lambda x: x, "abstractNote")

                # Metadata specific to different item types
                if self.item_type == "journalArticle":
                    self._safe_update(
                        match, "container-title", lambda x: x[0], "publicationTitle"
                    )
                    self._safe_update(match, "volume", lambda x: x, "volume")
                    self._safe_update(match, "issue", lambda x: x, "issue")

                if self.item_type in ["book", "bookSection", "report"]:
                    self._safe_update(match, "publisher", lambda x: x, "publisher")
                    self._safe_update(match, "publisher-location", lambda x: x, "place")

                self._safe_update(match, "page", lambda x: x, "pages")
                self._safe_update(
                    match, "issued.date-parts", self._process_date, "date"
                )
                self._safe_update(match, "DOI", lambda x: x, "DOI")

                if self.item_type == "book":
                    self._safe_update(match, "ISBN", lambda x: x[0], "ISBN")

                self._safe_update(match, "ISSN", lambda x: x[0], "ISSN")
                self._safe_update(match, "URL", lambda x: x, "url")
                self._safe_update(match, "language", lambda x: x, "language")

                return True

        except Exception as e:
            print(f"Error querying CrossRef for title: {self.title}\n{e}")
            self.failed_metadata_sources.append("crossref")

        return False

    def _safe_update(self, match_dict, key_path, transform_func, target_key):
        """
        Safely update a Zotero item key with CrossRef data.

        :param match_dict: Dictionary containing CrossRef data
        :param key_path: Dot-separated path to the key in the dictionary
        :param transform_func: Function to transform the value
        :param target_key: Key in the Zotero item to update
        """
        # Navigate through nested dictionaries
        current = match_dict
        for key in key_path.split("."):
            if current is None or not isinstance(current, (dict, list)):
                return
            current = current.get(key)

        if current is not None:
            try:
                transformed_value = transform_func(current)
                if transformed_value:
                    self.zotero_item[target_key] = transformed_value
            except Exception:
                pass

    def _process_authors(self, authors):
        """
        Process CrossRef author data into Zotero creator format.

        :param authors: List of author dictionaries from CrossRef
        :return: List of Zotero creator dictionaries
        """
        return [
            {
                "creatorType": "author" if len(authors) > 1 else "author",
                "firstName": m.get("given"),
                "lastName": m.get("family"),
            }
            for m in authors
            if m
        ]

    def _process_date(self, date_parts):
        """
        Process CrossRef date parts into a Zotero date string.

        :param date_parts: List of date parts from CrossRef
        :return: Formatted date string
        """
        if date_parts:
            return "-".join(str(x) for x in date_parts[0])
        return None

    def retrieve_metadata(self, sources=None):
        """
        Retrieve metadata from specified sources.

        :param sources: List of metadata sources to try. If None, tries all available sources.
        :return: True if metadata was successfully retrieved, False otherwise
        """
        sources = sources or list(self.metadata_sources.keys())

        for source in sources:
            if source in self.metadata_sources:
                if self.metadata_sources[source]():
                    return True

        return False

    def to_zotero_item(self):
        """
        Return the Zotero item representation.

        :return: Dictionary representing the Zotero item
        """
        return self.zotero_item
