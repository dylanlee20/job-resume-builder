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

    def is_blocked(self, key: str) -> bool:
        """Return True if the key is already at/over the limit.

        Unlike is_allowed, this does NOT record a hit. Use it to check a
        limit that should only be consumed on failure (e.g. login), so a
        legitimate request is never counted against the limit.
        """
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            timestamps = [t for t in self._store.get(key, []) if t > cutoff]
            self._store[key] = timestamps
            return len(timestamps) >= self._max

    def record(self, key: str) -> None:
        """Record a single hit against a key (e.g. one failed attempt)."""
        now = time.monotonic()
        with self._lock:
            timestamps = self._store.get(key, [])
            timestamps.append(now)
            self._store[key] = timestamps

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

# Login: 8 FAILED attempts per 15 minutes, tracked per IP and per username.
# Only failures are recorded (see is_blocked/record), and a successful login
# clears the counters, so ordinary users with the odd typo are never blocked.
login_limiter = RateLimiter(max_requests=8, window_seconds=900)
