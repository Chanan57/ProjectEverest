"""
Everest v8.0 — Cache Manager
Thread-safe, TTL-based in-memory cache for API responses.
Prevents API overuse by storing sentiment/news/macro results.
"""
import time
import threading


class CacheManager:
    """
    A lightweight, thread-safe, TTL-based in-memory cache.
    No external dependencies (no Redis needed for single-process bot).
    """

    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key):
        """
        Retrieve a cached value. Returns None if key doesn't exist or has expired.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.time() > entry["expires_at"]:
                del self._store[key]
                return None
            return entry["value"]

    def set(self, key, value, ttl_seconds):
        """
        Store a value with a time-to-live in seconds.
        """
        with self._lock:
            self._store[key] = {
                "value": value,
                "expires_at": time.time() + ttl_seconds,
                "created_at": time.time()
            }

    def is_valid(self, key):
        """
        Check if a key exists and hasn't expired, without retrieving the value.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            if time.time() > entry["expires_at"]:
                del self._store[key]
                return False
            return True

    def invalidate(self, key):
        """
        Force-expire a specific key.
        """
        with self._lock:
            self._store.pop(key, None)

    def clear(self):
        """
        Wipe the entire cache.
        """
        with self._lock:
            self._store.clear()

    def stats(self):
        """
        Return cache statistics for debugging/dashboard.
        """
        with self._lock:
            now = time.time()
            total = len(self._store)
            valid = sum(1 for e in self._store.values() if now <= e["expires_at"])
            expired = total - valid
            return {"total_keys": total, "valid": valid, "expired": expired}


# Module-level singleton — all modules share one cache instance
cache = CacheManager()

