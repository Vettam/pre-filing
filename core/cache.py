import time
from typing import Any


class InMemoryCache:
    def __init__(self):
        self._store: dict[str, tuple[Any, float | None]] = {}

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """
        Store a value under `key`.
        `ttl` is time-to-live in seconds. Pass None for no expiry.
        """
        expires_at = time.monotonic() + ttl if ttl is not None else None
        self._store[key] = (value, expires_at)

    def get(self, key: str) -> Any | None:
        """
        Retrieve a value by `key`. Returns None if missing or expired.
        """
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


cache = InMemoryCache()
