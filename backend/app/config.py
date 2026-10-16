"""Runtime configuration read from environment variables."""

import os


def allowed_origins() -> list[str]:
    """Origins allowed by CORS, from the comma-separated ALLOWED_ORIGINS env var.

    Unset or empty means no cross-origin access.
    """
    raw = os.environ.get("ALLOWED_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]
