from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

MiniLM_model = SentenceTransformer("all-MiniLM-L6-v2")


class SimilarityChecker:
    def __init__(self, model=MiniLM_model):
        self.model = model

    def compute_similarity(self, item1, item2) -> Optional[float]:
        if not item1 or not item2:
            return None
        if isinstance(item1, str) and isinstance(item2, str):
            return self.compare_text(item1, item2)
        if isinstance(item1, list) and isinstance(item2, list):
            return self.compare_list(item1, item2)
        else:
            return None

    def compare_text(self, text1: str, text2: str) -> float:
        embeddings = self.model.encode([text1, text2])
        similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        return float(similarity)

    def compare_list(self, list1: List[str], list2: List[str]) -> Optional[float]:
        if not list2:
            return None
        list1_embeddings = self.model.encode(list1)
        list2_embeddings = self.model.encode(list2)
        similarity = [
            max([cosine_similarity([l1], [l2])[0][0] for l2 in list2_embeddings])
            for l1 in list1_embeddings
        ]
        similarity = np.mean(similarity)
        return float(similarity)

    def author_similarity(
        self, scholar_authors: List[str], crossref_authors: List[str]
    ) -> Optional[float]:
        if not scholar_authors:
            return None
        return self.compare_list(scholar_authors, crossref_authors)

    def title_similarity(self, title1: str, title2: str) -> float:
        words1 = set(title1.lower().split())
        words2 = set(title2.lower().split())
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union) if union else 0.0

    def abstract_similarity(self, abstract1: str, abstract2: str) -> float:
        return self.compare_text(abstract1, abstract2)
