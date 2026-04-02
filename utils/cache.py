import threading
import time
from typing import Any


class TTLCache:
    """Simple thread-safe in-memory TTL cache."""

    def __init__(self, default_ttl: int = 3600):
        self.default_ttl = default_ttl
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None

            expires_at, value = item
            if expires_at <= time.time():
                self._store.pop(key, None)
                return None

            return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        effective_ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + max(1, effective_ttl)

        with self._lock:
            self._store[key] = (expires_at, value)

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def cleanup(self) -> int:
        """Remove expired entries and return removed count."""
        now = time.time()
        removed = 0

        with self._lock:
            expired_keys = [key for key, (expires_at, _) in self._store.items() if expires_at <= now]
            for key in expired_keys:
                self._store.pop(key, None)
                removed += 1

        return removed
