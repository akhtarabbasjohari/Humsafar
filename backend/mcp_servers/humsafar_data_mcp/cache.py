"""
Session-scoped TTL Cache for humsafar-data-mcp.
Prevents redundant live site scraping within the same conversation session.
"""

import time
import threading
from typing import Any, Optional, Dict, Tuple


class SessionScopedCache:
    """
    In-memory thread-safe cache scoped by session_id and key, with TTL expiration.
    Default TTL: 300 seconds (5 minutes).
    """

    def __init__(self, default_ttl_seconds: int = 300):
        self.default_ttl = default_ttl_seconds
        # Structure: { (session_id, key): (data, expire_at) }
        self._store: Dict[Tuple[str, str], Tuple[Any, float]] = {}
        self._lock = threading.RLock()

    def _make_key(self, session_id: str, key: str) -> Tuple[str, str]:
        return (session_id.strip() if session_id else "default", key.strip().lower())

    def get(self, session_id: str, key: str) -> Optional[Any]:
        """
        Retrieve a cached value if present and unexpired.
        """
        composite_key = self._make_key(session_id, key)
        with self._lock:
            entry = self._store.get(composite_key)
            if entry is None:
                return None

            data, expire_at = entry
            if time.time() > expire_at:
                # Expired
                del self._store[composite_key]
                return None

            return data

    def set(self, session_id: str, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Store a value with a specific TTL (in seconds).
        """
        composite_key = self._make_key(session_id, key)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expire_at = time.time() + ttl

        with self._lock:
            self._store[composite_key] = (value, expire_at)

    def clear_session(self, session_id: str) -> None:
        """
        Clear all cached entries belonging to a given session.
        """
        norm_session = session_id.strip() if session_id else "default"
        with self._lock:
            keys_to_delete = [k for k in self._store.keys() if k[0] == norm_session]
            for k in keys_to_delete:
                del self._store[k]

    def clear_expired(self) -> int:
        """
        Prune all expired entries. Returns count of purged items.
        """
        now = time.time()
        purged = 0
        with self._lock:
            keys_to_delete = [k for k, (_, expire_at) in self._store.items() if now > expire_at]
            for k in keys_to_delete:
                del self._store[k]
                purged += 1
        return purged

    def size(self) -> int:
        with self._lock:
            return len(self._store)


# Global singleton cache instance for the MCP server
global_cache = SessionScopedCache(default_ttl_seconds=300)
