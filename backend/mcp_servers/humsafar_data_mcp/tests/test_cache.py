"""
Unit tests for session-scoped TTL cache.
"""

import time
import pytest
from mcp_servers.humsafar_data_mcp.cache import SessionScopedCache


def test_cache_set_and_get():
    cache = SessionScopedCache(default_ttl_seconds=10)
    cache.set("session-1", "query:hunza", {"tours": ["Hunza Classic"]})

    result = cache.get("session-1", "query:hunza")
    assert result == {"tours": ["Hunza Classic"]}

    # Different session should not see the data
    assert cache.get("session-2", "query:hunza") is None


def test_cache_ttl_expiration():
    cache = SessionScopedCache(default_ttl_seconds=1)
    # Set with 0.1s TTL
    cache.set("session-1", "temp-key", "temporary_value", ttl_seconds=0.1)

    assert cache.get("session-1", "temp-key") == "temporary_value"
    time.sleep(0.15)
    assert cache.get("session-1", "temp-key") is None


def test_cache_clear_session():
    cache = SessionScopedCache(default_ttl_seconds=30)
    cache.set("sess-a", "k1", "data1")
    cache.set("sess-a", "k2", "data2")
    cache.set("sess-b", "k1", "data3")

    assert cache.size() == 3
    cache.clear_session("sess-a")

    assert cache.get("sess-a", "k1") is None
    assert cache.get("sess-a", "k2") is None
    assert cache.get("sess-b", "k1") == "data3"
