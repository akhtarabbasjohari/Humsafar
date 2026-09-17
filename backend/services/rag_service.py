"""
Retrieval-Augmented Generation (RAG) Service for Humsafar.
Provides semantic text chunking, dense vector embeddings, session-scoped vector indexing,
and top-K relevant chunk retrieval for web search fallback research.

Architectural Benefits:
1. Rate-Limit Mitigation: Passes concise, highly-relevant ~300-token chunks to Groq
   instead of multi-thousand token raw web scrape dumps, preventing HTTP 429 errors.
2. In-Session Caching & Reuse: Caches embedded chunks within the active session so follow-up
   inquiries query the session vector index without triggering redundant network scrapes.
3. Strict Provenance: Every retrieved chunk retains its source URL, title, and fresh timestamp.
"""

import re
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import faiss

from mcp_servers.humsafar_data_mcp.vector_store import (
    ItineraryEmbeddingEngine,
    global_embedding_engine,
    DEFAULT_EMBEDDING_DIM,
)

logger = logging.getLogger(__name__)


def chunk_text(text: str, chunk_size: int = 350, chunk_overlap: int = 50) -> List[str]:
    """
    Split a document or web scrape into overlapping semantic text chunks.
    Preserves sentence and paragraph boundaries where possible.
    """
    if not text:
        return []

    clean_text = re.sub(r"\s+", " ", text).strip()
    if len(clean_text) <= chunk_size:
        return [clean_text]

    # Split on sentence boundaries (.!? followed by space or newline)
    sentences = re.split(r"(?<=[.!?])\s+", clean_text)
    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        s_len = len(sentence)
        if current_length + s_len > chunk_size and current_chunk:
            chunk_str = " ".join(current_chunk).strip()
            if chunk_str:
                chunks.append(chunk_str)
            # Retain overlap from end of current chunk if possible
            overlap_words = []
            overlap_len = 0
            for w in reversed(chunk_str.split()):
                if overlap_len + len(w) + 1 <= chunk_overlap:
                    overlap_words.insert(0, w)
                    overlap_len += len(w) + 1
                else:
                    break
            current_chunk = overlap_words + [sentence]
            current_length = sum(len(x) + 1 for x in current_chunk)
        else:
            current_chunk.append(sentence)
            current_length += s_len + 1

    if current_chunk:
        chunk_str = " ".join(current_chunk).strip()
        if chunk_str and (not chunks or chunk_str != chunks[-1]):
            chunks.append(chunk_str)

    return chunks


class SessionRAGStore:
    """
    Session-isolated vector store maintaining FAISS indices of web research chunks.
    Allows rapid semantic retrieval and in-session reuse.
    """

    def __init__(self, embedding_engine: Optional[ItineraryEmbeddingEngine] = None):
        self.engine = embedding_engine or global_embedding_engine
        # Mapping: session_id -> { "index": faiss.IndexFlatIP, "chunks": List[Dict[str, Any]], "updated_at": str }
        self._session_stores: Dict[str, Dict[str, Any]] = {}

    def _get_or_create_store(self, session_id: str) -> Dict[str, Any]:
        sid = session_id or "default"
        if sid not in self._session_stores:
            self._session_stores[sid] = {
                "index": faiss.IndexFlatIP(DEFAULT_EMBEDDING_DIM),
                "chunks": [],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        return self._session_stores[sid]

    def has_session_data(self, session_id: str) -> bool:
        """Check if session vector index already contains indexed research chunks."""
        sid = session_id or "default"
        store = self._session_stores.get(sid)
        return bool(store and len(store["chunks"]) > 0)

    def index_research(
        self,
        session_id: str,
        web_research: Dict[str, Any],
        clear_existing: bool = False,
    ) -> int:
        """
        Chunk and embed multi-source research results (from 4-5 websites) into the session vector store.
        Returns the number of new chunks indexed.
        """
        store = self._get_or_create_store(session_id)
        if clear_existing:
            store["index"].reset()
            store["chunks"] = []

        now_iso = datetime.now(timezone.utc).isoformat()
        results = web_research.get("results", [])
        all_chunks_to_add: List[Dict[str, Any]] = []
        vectors_to_add: List[np.ndarray] = []

        for item in results:
            title = item.get("title", "External Tour Research")
            link = item.get("link", item.get("source_url", "https://visitpakistan.gov.pk"))
            content = item.get("content") or item.get("snippet") or ""

            if not content or len(content.strip()) < 30:
                continue

            # Split into distinct semantic text chunks
            text_chunks = chunk_text(content, chunk_size=320, chunk_overlap=40)
            for idx, chunk in enumerate(text_chunks):
                vec = self.engine.embed_text(f"{title} {chunk}")
                vectors_to_add.append(vec)
                all_chunks_to_add.append({
                    "title": title,
                    "source_url": link,
                    "chunk_index": idx,
                    "text": chunk,
                    "indexed_at": now_iso,
                })

        # Also chunk the synthesized research summary if present
        summary = web_research.get("research_summary", "")
        if summary and len(summary) > 100:
            sum_chunks = chunk_text(summary, chunk_size=320, chunk_overlap=40)
            for idx, sc in enumerate(sum_chunks):
                vec = self.engine.embed_text(f"Itinerary Research Summary: {sc}")
                vectors_to_add.append(vec)
                all_chunks_to_add.append({
                    "title": "Synthesized Travel Dossier",
                    "source_url": web_research.get("top_source_url", "https://visitpakistan.gov.pk"),
                    "chunk_index": idx,
                    "text": sc,
                    "indexed_at": now_iso,
                })

        if vectors_to_add:
            stacked_vecs = np.vstack(vectors_to_add).astype("float32")
            store["index"].add(stacked_vecs)
            store["chunks"].extend(all_chunks_to_add)
            store["updated_at"] = now_iso
            logger.info("Indexed %d semantic chunks into RAG store for session '%s'", len(all_chunks_to_add), session_id)

        return len(all_chunks_to_add)

    def retrieve_relevant_chunks(
        self,
        session_id: str,
        query: str,
        top_k: int = 3,
        min_score: float = 0.20,
    ) -> List[Dict[str, Any]]:
        """
        Embed the user query and retrieve top-K most relevant chunks from the session RAG store.
        """
        store = self._get_or_create_store(session_id)
        if not store["chunks"] or store["index"].ntotal == 0:
            return []

        query_vec = self.engine.embed_text(query).reshape(1, -1).astype("float32")
        k = min(top_k, store["index"].ntotal)
        scores, indices = store["index"].search(query_vec, k)

        retrieved = []
        seen_texts = set()

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(store["chunks"]):
                continue
            if score < min_score:
                continue

            chunk_meta = store["chunks"][idx]
            text = chunk_meta["text"]
            if text in seen_texts:
                continue
            seen_texts.add(text)

            retrieved.append({
                "title": chunk_meta["title"],
                "source_url": chunk_meta["source_url"],
                "text": text,
                "score": float(score),
                "indexed_at": chunk_meta["indexed_at"],
            })

        return retrieved

    def clear_session(self, session_id: str) -> None:
        """Purge indexed chunks for a completed session."""
        if session_id in self._session_stores:
            del self._session_stores[session_id]


rag_service = SessionRAGStore()
