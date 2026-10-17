"""Shared Gemini (Vertex AI) client, config and retry policy.

Used by bag classification (app/ai/classifier.py) and resident tips
(app/ai/tips.py) so both run on the same model, location, thinking level and
timeout (env vars, see app/config.py). Auth: Application Default Credentials.
"""

import logging
from collections.abc import Callable
from typing import Any, Literal

from app import config

logger = logging.getLogger(__name__)

RETRY_BACKOFF_S = 1.5


class AiError(Exception):
    """A Gemini call failed. `kind`: unavailable | invalid_output."""

    def __init__(self, kind: Literal["unavailable", "invalid_output"], message: str) -> None:
        super().__init__(message)
        self.kind = kind


def make_client(timeout_s: float | None = None, location: str | None = None) -> Any:  # noqa: ANN401
    from google import genai
    from google.genai import types

    return genai.Client(
        vertexai=True,
        project=config.project_id(),
        location=location or config.gemini_location(),
        http_options=types.HttpOptions(timeout=int((timeout_s or config.gemini_timeout_s()) * 1000)),
    )


def thinking_config(types: Any) -> Any:  # noqa: ANN401
    level = config.gemini_thinking_level()
    return types.ThinkingConfig(thinking_level=level) if level else None


def is_retryable(exc: Exception) -> bool:
    import httpx
    from google.genai import errors

    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError, TimeoutError)):
        return True
    if isinstance(exc, errors.APIError):
        return exc.code == 429 or (exc.code or 0) >= 500
    return False


def is_server_error(exc: Exception) -> bool:
    from google.genai import errors

    return isinstance(exc, errors.APIError) and (exc.code or 0) >= 500


def generate_with_retry(
    client: Any,  # noqa: ANN401
    model: str,
    contents: list[Any],
    generation_config: Any,  # noqa: ANN401
    sleep: Callable[[float], None],
    backoff_s: float = RETRY_BACKOFF_S,
    fallback_client: Any = None,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """generate_content with ONE retry (timeouts / 429 / 5xx); else AiError(unavailable).

    If `fallback_client` is given (tips only - aggregates, never photos) and the
    first attempt hit a 5xx, the retry goes to that client (global endpoint).
    """
    current = client
    for attempt in (1, 2):
        try:
            return current.models.generate_content(model=model, contents=contents, config=generation_config)
        except Exception as exc:  # noqa: BLE001 - classified below
            logger.warning("gemini attempt %d failed: %s", attempt, type(exc).__name__)
            if attempt == 2 or not is_retryable(exc):
                raise AiError("unavailable", f"Gemini request failed: {type(exc).__name__}") from exc
            if fallback_client is not None and is_server_error(exc):
                logger.warning("gemini regional 5xx: retrying on the global endpoint")
                current = fallback_client
            sleep(backoff_s)
    raise AssertionError("unreachable")
