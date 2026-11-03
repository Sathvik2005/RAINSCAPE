from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class CacheInfo:
    entries: int
    hits: int
    misses: int
    evictions: int


class BoundedTTLCache(Generic[T]):
    """Thread-safe process-local TTL/LRU cache with serialized cache fills."""

    def __init__(self, *, max_entries: int = 1, ttl_seconds: float = 600.0):
        if max_entries < 1 or ttl_seconds <= 0:
            raise ValueError("max_entries and ttl_seconds must be positive")
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._entries: OrderedDict[object, tuple[float, T]] = OrderedDict()
        self._lock = RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get_or_load(self, key: object, loader: Callable[[], T]) -> T:
        # The lock covers the load so identical concurrent misses perform one
        # expensive GRIB decode. This intentionally serializes different fills.
        with self._lock:
            now = monotonic()
            cached = self._entries.get(key)
            if cached is not None and cached[0] > now:
                self._entries.move_to_end(key)
                self._hits += 1
                return cached[1]
            if cached is not None:
                del self._entries[key]
            self._misses += 1
            value = loader()
            self._entries[key] = (monotonic() + self._ttl_seconds, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
                self._evictions += 1
            return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def info(self) -> CacheInfo:
        with self._lock:
            now = monotonic()
            expired = [key for key, (expiry, _) in self._entries.items() if expiry <= now]
            for key in expired:
                del self._entries[key]
            return CacheInfo(len(self._entries), self._hits, self._misses, self._evictions)
