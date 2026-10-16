"""Runtime configuration read from environment variables."""

import os


def allowed_origins() -> list[str]:
    """Origins allowed by CORS, from the comma-separated ALLOWED_ORIGINS env var.

    Unset or empty means no cross-origin access.
    """
    raw = os.environ.get("ALLOWED_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def project_id() -> str | None:
    """Google Cloud / Firebase project ID (GOOGLE_CLOUD_PROJECT)."""
    return os.environ.get("GOOGLE_CLOUD_PROJECT") or None


def demo_rate_limit() -> int:
    """Max demo sign-ins per client IP per minute (DEMO_RATE_LIMIT_PER_MIN)."""
    return int(os.environ.get("DEMO_RATE_LIMIT_PER_MIN", "10"))
