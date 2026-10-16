"""Simple in-memory sliding-window rate limiter (per Cloud Run instance)."""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


def client_ip(request: Request) -> str:
    """Client IP as seen by Cloud Run's front end.

    Cloud Run appends the real client IP to X-Forwarded-For, so the last entry
    is trustworthy; earlier entries can be spoofed by the caller.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    entries = [part.strip() for part in forwarded.split(",") if part.strip()]
    if entries:
        return entries[-1]
    return request.client.host if request.client else "unknown"


def enforce(limiter: RateLimiter, request: Request) -> str:
    """Raise 429 if the caller is over the limit; returns the client key."""
    key = client_ip(request)
    if not limiter.allow(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limited",
            headers={"Retry-After": str(int(limiter.window))},
        )
    return key
