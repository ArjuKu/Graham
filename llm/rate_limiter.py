import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Tuple


class GeminiRateLimitError(Exception):
    """Raised when any Gemini rate limit is hit."""
    pass


class GeminiDailyLimitError(Exception):
    """Raised when the daily request limit is hit."""
    pass


class RateLimiter:
    """
    Thread-safe rate limiter for Gemini 2.5 Flash.
    Enforces RPM, TPM, and RPD limits.
    """

    def __init__(self, config: dict):
        rl = config["rate_limits"]
        self.rpm_limit = rl["gemini_rpm_limit"]
        self.tpm_limit = rl["gemini_tpm_limit"]
        self.rpd_limit = rl["gemini_rpd_limit"]

        self._rpm_deque: Deque[float] = deque()
        self._tpm_deque: Deque[Tuple[float, int]] = deque()

        self._rpd_count = 0
        self._rpd_reset_time = self._get_next_reset()
        self._lock = threading.Lock()

    def _get_next_reset(self) -> datetime:
        """Get next midnight Pacific Time reset."""
        now = datetime.now(timezone.utc)
        pacific_offset = -8
        pacific_now = now.timestamp() + (pacific_offset * 3600)
        midnight_ts = (
            int(pacific_now // 86400) + 1
        ) * 86400 - (pacific_offset * 3600)
        return datetime.fromtimestamp(midnight_ts, tz=timezone.utc)

    def check_and_wait(self, estimated_tokens: int = 500):
        """
        Check limits and sleep if necessary to avoid exceeding them.
        Raises GeminiDailyLimitError if RPD is hit.
        """
        with self._lock:
            now = time.time()

            if now >= self._rpd_reset_time.timestamp():
                self._rpd_count = 0
                self._rpd_reset_time = self._get_next_reset()

            if self._rpd_count >= self.rpd_limit:
                reset_str = self._rpd_reset_time.strftime("%Y-%m-%d %H:%M:%S UTC")
                raise GeminiDailyLimitError(
                    f"Daily request limit reached ({self.rpd_limit}). Resets at {reset_str}"
                )

            while self._rpm_deque and (now - self._rpm_deque[0]) > 60:
                self._rpm_deque.popleft()

            while self._tpm_deque and (now - self._tpm_deque[0][0]) > 60:
                self._tpm_deque.popleft()

            current_rpm = len(self._rpm_deque)
            current_tpm = sum(t[1] for t in self._tpm_deque)

            if current_rpm >= self.rpm_limit:
                oldest = self._rpm_deque[0]
                sleep_time = 60 - (now - oldest)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            if current_tpm + estimated_tokens > self.tpm_limit:
                tokens_over = (current_tpm + estimated_tokens) - self.tpm_limit
                avg_tokens_per_sec = current_tpm / 60 if current_rpm > 0 else 1
                sleep_time = tokens_over / avg_tokens_per_sec
                if sleep_time > 0:
                    time.sleep(sleep_time)

    def record_call(self, tokens_used: int):
        """Record a successful API call."""
        with self._lock:
            now = time.time()
            self._rpm_deque.append(now)
            self._tpm_deque.append((now, tokens_used))
            self._rpd_count += 1
