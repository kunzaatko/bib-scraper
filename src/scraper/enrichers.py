import logging
import re
from abc import ABC, abstractmethod
from textwrap import wrap
from typing import List, Optional

import requests
from rich.table import Table

from .similarity import SimilarityChecker
from .utils import log_table


class AbstractMetadataEnricher(ABC):
    @abstractmethod
    def enrich(
        self, title: str, abstract: Optional[str], authors: Optional[List[str]]
    ) -> Optional[dict]:
        """Enrich metadata for the given title, abstract and authors. Return dict of enriched data or None."""
        pass


class CrossrefEnricher(AbstractMetadataEnricher):
    CROSSREF_URL = "https://api.crossref.org/works"

    CROSSREF_ITEM_TYPE_MAPPING = {
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

    def __init__(self, similarity_threshold: float = 0.7):
        self.similarity_checker = SimilarityChecker()
        self.similarity_threshold = similarity_threshold
        self.logger = logging.getLogger(__name__)
        self.score_weights = {"author": 0.5, "title": 0.5}

    def with_logger(self, logger: logging.Logger):
        self.logger = logger
        return self

    def enrich(
        self, title: str, abstract: Optional[str], authors: Optional[List[str]]
    ) -> Optional[dict]:
        if not title:
            self.logger.error("Title is empty")
            return None

        params = {
            "query.title": title,
            "rows": 5,
        }  # Get more results for comparison
        try:
            response = requests.get(self.CROSSREF_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if not data["message"]["items"]:
                return None

            # Find matches using new similarity scheme
            matches = []
            for item in data["message"]["items"]:
                scores = self._compute_match_score(title, abstract, authors, item)
                weighted = self.weighted_score(scores)
                if weighted >= self.similarity_threshold:
                    matches.append((item, scores, weighted))

            if not matches:
                self.logger.warning(
                    f'No suitable match found for title: "{title}". No matches met the threshold {self.similarity_threshold}.'
                )
                return None

            # Sort by weighted score
            matches.sort(key=lambda x: x[2], reverse=True)

            # Sort matches by quality
            if abstract and len(matches) > 1:
                # Use abstract similarity for ranking
                matches_with_abstract = []
                for match in matches:
                    item, scores, weighted = match
                    if scores["abstract"]:
                        matches_with_abstract.append((item, scores["abstract"]))
                matches_with_abstract.sort(key=lambda x: x[1], reverse=True)
                sorted_matches = [item for item, _ in matches_with_abstract]
                for item, _, weighted in matches:
                    if item not in sorted_matches:
                        sorted_matches.append(item)
                best_score = matches_with_abstract[0][1]
            else:
                sorted_matches = [item for item, _, _ in matches]
                best_score = matches[0][2]

            # Process all matches, preferring the best
            enriched = self._process_matches(sorted_matches)
            self.logger.debug(
                f'Enriched with best score {best_score:.5f}: "{enriched.get("title", "N/A")}"'
            )
            return enriched

        except Exception as e:
            self.logger.error(f'Error querying CrossRef for title: "{title}"\n{e}')
            return None

    def weighted_score(self, scores: dict) -> float:
        score_weights = self.score_weights
        for k, v in scores.items():
            if k in score_weights:
                if not v:
                    score_weights.pop(k)
        for k in score_weights.keys():
            if k not in scores.keys():
                score_weights.pop(k)
        score_weights = {
            k: v / sum(score_weights.values()) for k, v in score_weights.items()
        }
        weighted = sum(
            [score_weights[k] * v for k, v in scores.items() if k in score_weights]
        )
        return weighted

    def _compute_match_score(
        self,
        title: str,
        abstract: Optional[str],
        authors: Optional[List[str]],
        crossref_item: dict,
    ) -> dict:
        scholar_title = title
        scholar_abstract = abstract or ""
        scholar_authors = [a.split()[-1] for a in authors] if authors else []
        crossref_title = (
            crossref_item.get("title", [""])[0] if crossref_item.get("title") else ""
        )
        crossref_abstract = self._extract_abstract(crossref_item)
        crossref_authors = [
            a.get("family", "") for a in crossref_item.get("author", [])
        ]

        author_score = self.similarity_checker.author_similarity(
            scholar_authors, crossref_authors
        )
        title_score = self.similarity_checker.title_similarity(
            scholar_title, crossref_title
        )
        abstract_score = (
            self.similarity_checker.abstract_similarity(
                scholar_abstract, crossref_abstract
            )
            if scholar_abstract
            else None
        )

        scores = {
            "author": author_score,
            "title": title_score,
            "abstract": abstract_score,
        }

        similarity_table = Table(title="Similarity scores", show_lines=True)
        similarity_table.add_column("GoogleScholar")
        similarity_table.add_column("CrossRef")
        similarity_table.add_column("similarity")
        similarity_table.add_row(
            "\n".join(wrap(scholar_title)),
            "\n".join(wrap(crossref_title)),
            f"{title_score:.5f}",
        )
        similarity_table.add_row(
            "\n".join(wrap(scholar_abstract)),
            "\n".join(wrap(crossref_abstract)),
            f"{abstract_score:.5f}" if abstract_score else "None",
        )
        similarity_table.add_row(
            "\n".join(wrap(", ".join(scholar_authors))),
            "\n".join(wrap(", ".join(crossref_authors))),
            f"{author_score:.5f}" if author_score else "None",
        )
        self.logger.debug(
            f"{log_table(similarity_table)}\n[bold]\tTotal (weighted):\t {self.weighted_score(scores):.5f}[/bold]",
            extra={"markup": True},
        )

        return scores

    def _extract_abstract(self, crossref_item: dict) -> str:
        abstract = crossref_item.get("abstract", "")
        if abstract:
            return re.compile(r"</?jats:p>").sub("", abstract).strip()
        return ""

    def _process_matches(self, matches: List[dict]) -> dict:
        enriched = {}

        for match in matches:
            # Title
            if not enriched.get("title") and match.get("title"):
                enriched["title"] = match["title"][0]

            # Authors
            if not enriched.get("creators") and match.get("author"):
                enriched["creators"] = [
                    {
                        "creatorType": "author",
                        "firstName": m.get("given", ""),
                        "lastName": m.get("family", ""),
                    }
                    for m in match["author"]
                    if m
                ]

            # Abstract
            if not enriched.get("abstractNote") and match.get("abstract"):
                enriched["abstractNote"] = self._extract_abstract(match)

            # Item type
            if not enriched.get("itemType"):
                crossref_type = match.get("type", "journal-article")
                enriched["itemType"] = self.CROSSREF_ITEM_TYPE_MAPPING.get(
                    crossref_type, "journalArticle"
                )

            # Other fields
            if not enriched.get("publicationTitle") and match.get("container-title"):
                enriched["publicationTitle"] = match["container-title"][0]
            if not enriched.get("volume") and match.get("volume"):
                enriched["volume"] = match["volume"]
            if not enriched.get("issue") and match.get("issue"):
                enriched["issue"] = match["issue"]
            if not enriched.get("publisher") and match.get("publisher"):
                enriched["publisher"] = match["publisher"]
            if not enriched.get("place") and match.get("publisher-location"):
                enriched["place"] = match["publisher-location"]
            if not enriched.get("pages") and match.get("page"):
                enriched["pages"] = match["page"]
            if not enriched.get("date") and match.get("issued", {}).get("date-parts"):
                enriched["date"] = "-".join(
                    str(x) for x in match["issued"]["date-parts"][0]
                )
            if not enriched.get("DOI") and match.get("DOI"):
                enriched["DOI"] = match["DOI"]
            if not enriched.get("ISBN") and match.get("ISBN"):
                enriched["ISBN"] = (
                    match["ISBN"][0]
                    if isinstance(match["ISBN"], list)
                    else match["ISBN"]
                )
            if not enriched.get("ISSN") and match.get("ISSN"):
                enriched["ISSN"] = (
                    match["ISSN"][0]
                    if isinstance(match["ISSN"], list)
                    else match["ISSN"]
                )
            if not enriched.get("url") and match.get("URL"):
                enriched["url"] = match["URL"]
            if not enriched.get("language") and match.get("language"):
                enriched["language"] = match["language"]

        self.logger.debug(f"Enriched match data: {enriched}")

        return enriched
