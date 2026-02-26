"""In-memory rate limiter for abuse protection.

TODO: Replace with Redis-backed limiter for multi-process deployments.
"""
import threading
import time


class RateLimiter:
    """Simple in-memory sliding-window rate limiter.

    Tracks timestamps per key and rejects requests that exceed
    the configured limit within the window.
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self._max = max_requests
        self._window = window_seconds
        self._store: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        """Return True if the request is allowed, False if rate-limited."""
        now = time.monotonic()
        cutoff = now - self._window

        with self._lock:
            timestamps = self._store.get(key, [])
            # Prune expired entries
            timestamps = [t for t in timestamps if t > cutoff]

            if len(timestamps) >= self._max:
                self._store[key] = timestamps
                return False

            timestamps.append(now)
            self._store[key] = timestamps
            return True

    def reset(self, key: str) -> None:
        """Clear rate limit state for a key (useful in tests)."""
        with self._lock:
            self._store.pop(key, None)

    def cleanup(self) -> None:
        """Remove all expired entries. Call periodically to free memory."""
        now = time.monotonic()
        with self._lock:
            empty_keys = []
            for key, timestamps in self._store.items():
                self._store[key] = [t for t in timestamps if t > now - self._window]
                if not self._store[key]:
                    empty_keys.append(key)
            for key in empty_keys:
                del self._store[key]


# Shared instances for auth endpoints
# Register: 5 attempts per 15 minutes per IP
register_limiter = RateLimiter(max_requests=5, window_seconds=900)

# Resend verification: 3 attempts per 5 minutes per email
resend_limiter = RateLimiter(max_requests=3, window_seconds=300)
