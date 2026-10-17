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


# --- Gemini (Vertex AI) ---


def gemini_model() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")


def gemini_location() -> str:
    """Vertex AI location; asia-south1 keeps photos in-region."""
    return os.environ.get("GEMINI_LOCATION", "asia-south1")


def gemini_thinking_level() -> str | None:
    """minimal | low | medium | high, or empty to use the model default."""
    return os.environ.get("GEMINI_THINKING_LEVEL", "minimal") or None


def gemini_timeout_s() -> float:
    return float(os.environ.get("GEMINI_TIMEOUT_S", "25"))


def gemini_tips_timeout_s() -> float:
    """Tips are nice-to-have: fail fast to the fallback (GEMINI_TIPS_TIMEOUT_S)."""
    return float(os.environ.get("GEMINI_TIPS_TIMEOUT_S", "10"))


def partner_rate_limit() -> int:
    """Partner API requests per key per minute (PARTNER_RATE_LIMIT_PER_MIN)."""
    return int(os.environ.get("PARTNER_RATE_LIMIT_PER_MIN", "60"))


def tips_rate_limit() -> int:
    """Max Gemini tip generations per resident per minute (TIPS_RATE_LIMIT_PER_MIN)."""
    return int(os.environ.get("TIPS_RATE_LIMIT_PER_MIN", "10"))


def analyze_rate_limit() -> int:
    """Max Gemini analyses per operator per minute (ANALYZE_RATE_LIMIT_PER_MIN)."""
    return int(os.environ.get("ANALYZE_RATE_LIMIT_PER_MIN", "10"))


# --- Cloud Storage ---


def photo_bucket() -> str:
    return os.environ.get("PHOTO_BUCKET", "ecotrace-9e406-bag-photos")
