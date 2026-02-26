"""Tests for the in-memory rate limiter."""
import time

import pytest

from utils.rate_limiter import RateLimiter


class TestRateLimiter:

    def test_allows_within_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        assert limiter.is_allowed('key1') is True
        assert limiter.is_allowed('key1') is True
        assert limiter.is_allowed('key1') is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.is_allowed('key1') is True
        assert limiter.is_allowed('key1') is True
        assert limiter.is_allowed('key1') is False

    def test_different_keys_independent(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_allowed('key-a') is True
        assert limiter.is_allowed('key-b') is True
        assert limiter.is_allowed('key-a') is False

    def test_window_expiry_allows_again(self):
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        assert limiter.is_allowed('key1') is True
        assert limiter.is_allowed('key1') is False
        time.sleep(1.1)  # Wait for window to expire
        assert limiter.is_allowed('key1') is True

    def test_reset_clears_key(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_allowed('key1') is True
        assert limiter.is_allowed('key1') is False
        limiter.reset('key1')
        assert limiter.is_allowed('key1') is True

    def test_cleanup_removes_expired(self):
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        limiter.is_allowed('key1')
        time.sleep(1.1)
        limiter.cleanup()
        # After cleanup, store should be empty
        assert limiter._store == {}
