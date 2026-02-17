"""Tests for sliding window rate limiter."""
import time

from src.api.middleware.rate_limit import SlidingWindowCounter


class TestSlidingWindowCounter:
    def test_allows_within_limit(self):
        counter = SlidingWindowCounter()
        for _ in range(5):
            allowed, _, remaining = counter.is_allowed("client1", limit=5, window_seconds=60)
            assert allowed is True
            assert remaining >= 0

    def test_blocks_over_limit(self):
        counter = SlidingWindowCounter()
        for _ in range(3):
            counter.is_allowed("client1", limit=3, window_seconds=60)
        allowed, retry_after, remaining = counter.is_allowed("client1", limit=3, window_seconds=60)
        assert allowed is False
        assert retry_after >= 1
        assert remaining == 0

    def test_separate_keys(self):
        counter = SlidingWindowCounter()
        counter.is_allowed("ip-a", limit=2, window_seconds=60)
        counter.is_allowed("ip-a", limit=2, window_seconds=60)
        allowed_a, _, _ = counter.is_allowed("ip-a", limit=2, window_seconds=60)
        allowed_b, _, _ = counter.is_allowed("ip-b", limit=2, window_seconds=60)
        assert allowed_a is False
        assert allowed_b is True

    def test_window_expiry(self):
        counter = SlidingWindowCounter()
        counter.is_allowed("expire-test", limit=1, window_seconds=0.1)
        allowed, _, _ = counter.is_allowed("expire-test", limit=1, window_seconds=0.1)
        assert allowed is False
        time.sleep(0.15)
        allowed, _, _ = counter.is_allowed("expire-test", limit=1, window_seconds=0.1)
        assert allowed is True

    def test_retry_after_is_positive(self):
        counter = SlidingWindowCounter()
        counter.is_allowed("retry-key", limit=1, window_seconds=60)
        _, retry_after, _ = counter.is_allowed("retry-key", limit=1, window_seconds=60)
        assert retry_after >= 1

    def test_remaining_count(self):
        counter = SlidingWindowCounter()
        _, _, remaining = counter.is_allowed("rem-key", limit=5, window_seconds=60)
        assert remaining == 4
        _, _, remaining = counter.is_allowed("rem-key", limit=5, window_seconds=60)
        assert remaining == 3
