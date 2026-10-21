from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class CacheStats:
    entries: int
    hits: int
    misses: int


@dataclass(slots=True)
class _Entry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must be non-negative")
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[str, _Entry[T]] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> T | None:
        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.expires_at <= self._clock():
            del self._entries[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry.value

    def set(self, key: str, value: T) -> None:
        self._entries[key] = _Entry(value=value, expires_at=self._clock() + self._ttl_seconds)

    def clear(self) -> None:
        self._entries.clear()

    @property
    def stats(self) -> CacheStats:
        return CacheStats(entries=len(self._entries), hits=self._hits, misses=self._misses)
