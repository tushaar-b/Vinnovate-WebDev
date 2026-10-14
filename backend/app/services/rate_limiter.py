import time
import random
import email.utils
from urllib.parse import urlsplit
from typing import Optional
from app.config import settings
from app.redis_client import redis_client


def get_domain_from_url(url: str) -> str:
    """Extracts lowercase hostname/domain from a URL."""
    try:
        parsed = urlsplit(url)
        return (parsed.hostname or "default").lower()
    except Exception:
        return "default"


class DomainRateLimiter:
    """
    Manages per-domain concurrency, cooldown intervals, and retry backoff using Redis.
    """

    def __init__(self, redis_conn=None):
        self.r = redis_conn or redis_client

    def acquire_domain_lock(self, domain: str, timeout_seconds: int = 90) -> bool:
        """
        Attempts to acquire an exclusive concurrency lock for a domain.
        Prevents multiple workers from hitting the same domain simultaneously.
        """
        if settings.TEST_MODE:
            # In test mode, lock acquisition is immediate unless testing rate limiting explicitly
            pass
        lock_key = f"lock:domain:{domain}"
        # Set if not exists with TTL
        acquired = self.r.set(lock_key, "1", nx=True, ex=timeout_seconds)
        return bool(acquired)

    def release_domain_lock(self, domain: str) -> None:
        """Releases the domain concurrency lock."""
        lock_key = f"lock:domain:{domain}"
        try:
            self.r.delete(lock_key)
        except Exception:
            pass

    def get_domain_cooldown_remaining(self, domain: str) -> int:
        """
        Returns remaining seconds for domain cooldown. Returns 0 if no cooldown active.
        """
        cooldown_key = f"cooldown:domain:{domain}"
        ttl = self.r.ttl(cooldown_key)
        return max(0, ttl) if ttl > 0 else 0

    def set_domain_cooldown(self, domain: str, duration_seconds: Optional[int] = None) -> None:
        """
        Sets a cooldown spacing on a domain.
        Default spacing is 10s (or 0s in TEST_MODE unless explicitly specified).
        """
        if duration_seconds is None:
            duration_seconds = 0 if settings.TEST_MODE else 10
        if duration_seconds > 0:
            cooldown_key = f"cooldown:domain:{domain}"
            self.r.set(cooldown_key, "1", ex=duration_seconds)

    @staticmethod
    def parse_retry_after(header_value: Optional[str]) -> Optional[int]:
        """
        Parses the Retry-After HTTP header value.
        Supports integer seconds or HTTP-date format (RFC 7231).
        """
        if not header_value:
            return None
        header_clean = header_value.strip()
        # 1. Try integer seconds
        if header_clean.isdigit():
            return max(1, min(int(header_clean), 120))
        # 2. Try HTTP date format
        try:
            parsed_date = email.utils.parsedate_to_datetime(header_clean)
            diff = (parsed_date.timestamp() - time.time())
            return max(1, min(int(diff), 120))
        except Exception:
            return None

    @staticmethod
    def is_retryable_error(error_code: Optional[str], http_status: Optional[int]) -> bool:
        """
        Classifies errors as retryable or non-retryable:
        Retryable:
        - Network timeouts (TIMEOUT)
        - Transient connection errors (NAVIGATION_ERROR)
        - HTTP 502/503/504 (HTTP_5XX)
        - HTTP 429 Too Many Requests
        Non-retryable:
        - SSRF / security violations (BLOCKED_TARGET)
        - Authentication / captcha / forbidden (BLOCKED, 401, 403)
        - HTTP 404 / 400 (HTTP_4XX)
        - Missing selectors (MISSING_SELECTOR)
        """
        if http_status == 429:
            return True
        if http_status in (502, 503, 504):
            return True
        if error_code in ("TIMEOUT", "NAVIGATION_ERROR", "HTTP_5XX"):
            return True
        return False

    @staticmethod
    def calculate_backoff_delay(attempt: int, base_seconds: float = 2.0, max_seconds: float = 30.0) -> float:
        """
        Calculates bounded exponential backoff with jitter:
        delay = min(base * (2 ** (attempt - 1)) + jitter, max_seconds)
        """
        jitter = random.uniform(0.1, 0.5)
        backoff = base_seconds * (2 ** max(0, attempt - 1)) + jitter
        return min(backoff, max_seconds)


rate_limiter = DomainRateLimiter()
