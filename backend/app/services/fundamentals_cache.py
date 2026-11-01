"""Lightweight in-process cache for expensive fundamental assessments.

Invalidated when underlying financial data changes (refresh completion).
Does not call Yahoo Finance.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Hashable


class FundamentalsCache:
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._store: dict[Hashable, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._generation = 0

    def get(self, key: Hashable) -> Any | None:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, value = item
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.time() + self.ttl_seconds, value)

    def invalidate_all(self) -> None:
        with self._lock:
            self._store.clear()
            self._generation += 1

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation


analysis_cache = FundamentalsCache(ttl_seconds=3600)
