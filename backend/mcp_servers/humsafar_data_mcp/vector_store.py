"""
Vector store and dense semantic embedding engine for humsafar-data-mcp.
Enables retrieval-augmented matching so search_itineraries no longer relies strictly on exact keyword matching.
Supports loosely worded queries, destination nicknames, and partial names.
Preserves original scrape timestamps and confidence labels adhering to Phase 4 freshness rules.
"""

import re
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import faiss

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_DIM = 384

# Semantic synonym clusters for Northern Pakistan trekking and expeditions
# Ensures queries using nicknames, landmark descriptions, or partial names
# map into the same dense semantic coordinate space as official tour packages.
DOMAIN_SYNONYM_CLUSTERS = [
    {
        "cluster": "k2_concordia",
        "terms": [
            "k2", "k2 base camp", "concordia", "concordia trek", "baltoro", "baltoro glacier",
            "godwin-austen", "godwin austen", "savage mountain", "gilkey memorial", "gilkey",
            "throne room of mountain gods", "throne room", "broad peak", "mitre peak",
            "gasherbrum", "askole", "urdukas", "goro", "paiju"
        ],
    },
    {
        "cluster": "spantik_golden_peak",
        "terms": [
            "spantik", "spantik peak", "spantik expedition", "golden peak", "chogo lungma",
            "chogo lungma glacier", "arandu", "bolocho", "chogo brangsa"
        ],
    },
    {
        "cluster": "hunza_autumn_passu",
        "terms": [
            "hunza", "hunza autumn", "hunza tour", "karimabad", "baltit fort", "baltit",
            "altit fort", "altit", "duikar", "eagles nest", "eagle nest", "passu cones",
            "passu", "cathedral spires", "cathedrals", "attabad lake", "attabad", "borith lake",
            "borith", "khunjerab pass", "khunjerab", "rakaposhi view", "rakaposhi", "nagar"
        ],
    },
    {
        "cluster": "fairy_meadows_nanga_parbat",
        "terms": [
            "fairy meadows", "fairy meadow", "nanga parbat", "nanga parbat base camp",
            "killer mountain", "raikot bridge", "raikot", "tato village", "beyal camp"
        ],
    },
    {
        "cluster": "skardu_deosai",
        "terms": [
            "skardu", "deosai", "deosai plains", "land of giants", "sheosar lake", "sheosar",
            "shangrila", "lower kachura", "upper kachura", "kachura lake", "katpana desert",
            "cold desert", "shigar fort", "shigar", "khaplu palace", "khaplu", "sadpara"
        ],
    },
    {
        "cluster": "gondogoro_la",
        "terms": [
            "gondogoro", "gondogoro la", "gl pass", "ali camp", "khuspang", "hushe", "hushe valley"
        ],
    },
    {
        "cluster": "nangma_trango",
        "terms": [
            "nangma", "nangma valley", "amin brakk", "trango", "trango towers", "nameless tower",
            "great trango"
        ],
    },
    {
        "cluster": "swat_kalam",
        "terms": [
            "swat", "swat valley", "kalam", "ushuk", "mahodand lake", "mahodand", "malam jabba"
        ],
    },
    {
        "cluster": "chitral_kalash",
        "terms": [
            "chitral", "kalash", "kalash valley", "bumburet", "rambur", "birir", "tirich mir", "shandur"
        ],
    },
]


class ItineraryEmbeddingEngine:
    """
    Deterministic dense semantic embedding generator.
    Produces L2-normalized float32 vectors in dimension D=384.
    Combines subword n-gram hashing with domain semantic cluster projections
    to ensure high cosine similarity between queries and relevant itineraries,
    even with loose wording, nicknames, or partial names.
    """

    def __init__(self, dim: int = DEFAULT_EMBEDDING_DIM):
        self.dim = dim
        self._synonym_map: Dict[str, int] = {}
        # Allocate dedicated subspace dimensions (0 to 63) for domain clusters
        for idx, cluster_info in enumerate(DOMAIN_SYNONYM_CLUSTERS):
            cluster_dim = idx % 64
            for term in cluster_info["terms"]:
                self._synonym_map[term.lower()] = cluster_dim

    def _hash_token(self, token: str, seed: int = 0) -> int:
        """Deterministic integer hash for a token/n-gram."""
        h = hashlib.sha256(f"{seed}:{token}".encode("utf-8")).digest()
        val = int.from_bytes(h[:4], byteorder="big", signed=False)
        return val

    def extract_searchable_text(self, item: Dict[str, Any]) -> str:
        """
        Extract rich textual representation from itinerary dictionary.
        Combines title, summary, region, duration, highlights, and schedule.
        """
        parts = []
        title = item.get("title", "")
        if title:
            # Title carries double weight
            parts.extend([title, title])

        summary = item.get("summary", "")
        if summary:
            parts.append(summary)

        region = item.get("region", "")
        if region:
            parts.append(region)

        entity_type = item.get("entity_type", "")
        if entity_type:
            parts.append(entity_type)

        duration = item.get("duration", "")
        if duration:
            parts.append(f"Duration: {duration}")

        highlights = item.get("highlights", [])
        if isinstance(highlights, list):
            for hl in highlights:
                if isinstance(hl, str):
                    parts.append(hl)

        # Schedule stages
        schedule = item.get("itinerary_schedule") or item.get("day_by_day") or []
        if isinstance(schedule, list):
            for stage in schedule:
                if isinstance(stage, dict):
                    st_title = stage.get("title", "")
                    st_desc = stage.get("description", "")
                    st_alt = stage.get("altitude", "")
                    stage_line = f"{st_title} {st_desc} {st_alt}".strip()
                    if stage_line:
                        parts.append(stage_line)
                elif isinstance(stage, str):
                    parts.append(stage)

        inclusions = item.get("inclusions", [])
        if isinstance(inclusions, list):
            parts.extend([inc for inc in inclusions if isinstance(inc, str)])

        return " ".join(parts)

    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate a dense float32 unit vector (shape: (1, dim)) for a text string.
        """
        vec = np.zeros(self.dim, dtype=np.float32)
        if not text or not text.strip():
            return vec.reshape(1, -1)

        cleaned = text.lower()
        words = re.findall(r"\b[a-z0-9\-\']+\b", cleaned)

        # 1. Domain Semantic Cluster Projection
        # Check for multi-word and single-word synonyms
        for term, cluster_dim in self._synonym_map.items():
            if " " in term:
                if term in cleaned:
                    vec[cluster_dim] += 3.0
            else:
                if term in words:
                    vec[cluster_dim] += 2.0

        # 2. Word & Subword Character N-Gram Hashing (Subspace 64 to dim-1)
        subspace_start = 64
        subspace_len = self.dim - subspace_start

        for word in words:
            # Word level hashing
            w_idx = subspace_start + (self._hash_token(word, seed=42) % subspace_len)
            vec[w_idx] += 1.0

            # Character 3-grams, 4-grams for partial match tolerance
            if len(word) >= 3:
                for n in (3, 4):
                    for i in range(len(word) - n + 1):
                        ngram = word[i:i + n]
                        ng_idx = subspace_start + (self._hash_token(ngram, seed=1337) % subspace_len)
                        vec[ng_idx] += 0.35

        # 3. L2 Unit Normalization (Cosine Similarity Space)
        norm = np.linalg.norm(vec)
        if norm > 1e-9:
            vec = vec / norm

        return vec.reshape(1, -1)


class ItineraryVectorStore:
    """
    Lightweight local vector store backed by FAISS IndexFlatIP (Cosine Similarity).
    Stores dense embeddings alongside raw itinerary metadata.
    Enforces Phase 4 data freshness integrity by strictly preserving original
    scrape timestamps ('scraped_at') and source URLs.
    """

    def __init__(self, embedding_engine: Optional[ItineraryEmbeddingEngine] = None):
        self.embedding_engine = embedding_engine or ItineraryEmbeddingEngine()
        self.dim = self.embedding_engine.dim
        self.index = faiss.IndexFlatIP(self.dim)
        self.documents: List[Dict[str, Any]] = []
        self._doc_id_map: Dict[str, int] = {}  # url/key -> index

    def _make_key(self, item: Dict[str, Any]) -> str:
        """Derive unique key for deduplication."""
        return (item.get("url") or item.get("source_url") or item.get("title") or "").strip().lower()

    def add_or_update(self, item: Dict[str, Any]) -> int:
        """
        Embed an itinerary and store it in FAISS.
        If the itinerary already exists (by URL/title), updates the metadata.
        Preserves original 'scraped_at' and 'source_url' metadata.
        """
        key = self._make_key(item)
        doc = dict(item)

        # Ensure timestamp is preserved or initialized
        if not doc.get("scraped_at"):
            doc["scraped_at"] = datetime.now(timezone.utc).isoformat()

        text = self.embedding_engine.extract_searchable_text(doc)
        vec = self.embedding_engine.embed_text(text)

        if key and key in self._doc_id_map:
            # Update existing document metadata and rebuild index to preserve sync
            idx = self._doc_id_map[key]
            self.documents[idx] = doc
            self._rebuild_index()
            return idx

        # Append new item
        idx = len(self.documents)
        self.documents.append(doc)
        if key:
            self._doc_id_map[key] = idx
        self.index.add(vec)
        return idx

    def add_batch(self, items: List[Dict[str, Any]]) -> int:
        """Add multiple itineraries to the vector store."""
        count = 0
        for it in items:
            self.add_or_update(it)
            count += 1
        return count

    def _rebuild_index(self) -> None:
        """Rebuild FAISS index from stored documents."""
        self.index = faiss.IndexFlatIP(self.dim)
        if not self.documents:
            return
        vectors = []
        for doc in self.documents:
            text = self.embedding_engine.extract_searchable_text(doc)
            vec = self.embedding_engine.embed_text(text)
            vectors.append(vec[0])
        vec_matrix = np.vstack(vectors).astype(np.float32)
        self.index.add(vec_matrix)

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        min_score: float = 0.20,
    ) -> List[Dict[str, Any]]:
        """
        Embed query_text and retrieve top_k closest matching itinerary candidates.
        Returns matching itinerary items augmented with:
        - _retrieval_score: float (cosine similarity)
        - _retrieval_method: 'vector_store'
        Strictly preserves original scraped_at and source_url metadata.
        """
        if self.index.ntotal == 0 or not query_text or not query_text.strip():
            return []

        q_vec = self.embedding_engine.embed_text(query_text)
        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(q_vec, k)

        matched: List[Dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.documents):
                continue
            if float(score) < min_score:
                continue

            doc_copy = dict(self.documents[idx])
            doc_copy["_retrieval_score"] = float(score)
            doc_copy["_retrieval_method"] = "vector_store"
            matched.append(doc_copy)

        return matched

    def size(self) -> int:
        """Return number of indexed documents."""
        return len(self.documents)

    def clear(self) -> None:
        """Reset the vector store and FAISS index."""
        self.index = faiss.IndexFlatIP(self.dim)
        self.documents.clear()
        self._doc_id_map.clear()


# Global vector store instance for humsafar-data-mcp
global_vector_store = ItineraryVectorStore()
