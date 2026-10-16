"""Time source, injectable so date rules are testable."""

from datetime import UTC, date, datetime, timedelta, timezone
from typing import Protocol

# Sri Lanka has no DST, so a fixed offset avoids needing tzdata in the image.
COLOMBO = timezone(timedelta(hours=5, minutes=30), "Asia/Colombo")


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def local_today(clock: Clock) -> date:
    """Today's date in Colombo."""
    return clock.now().astimezone(COLOMBO).date()
