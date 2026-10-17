"""Gemini classifier: structured-output parsing, retry/timeout, error mapping."""

import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from google.genai import errors, types

from app.ai.classifier import SYSTEM_INSTRUCTION, AiError, GeminiClassifier, parse_ai_output

GOOD = {
    "items": [
        {"name": "PET bottle", "category": "plastic", "material": "PET", "productType": "water bottle",
         "brand": "Aqua", "quantity": 2, "recyclable": True, "confidence": 0.93},
        {"name": "banana peel", "category": "organic", "material": "food", "productType": "peel",
         "brand": None, "quantity": 1, "recyclable": False, "confidence": 0.55},
    ],
    "segregationQuality": "poor",
    "hazardFlags": ["battery"],
    "notes": "Food mixed with recyclables.",
}


# --- parsing ---


def test_parses_valid_structured_output() -> None:
    result = parse_ai_output(GOOD)
    assert [i.name for i in result.items] == ["PET bottle", "banana peel"]
    assert result.items[0].brand == "Aqua"
    assert result.segregationQuality == "poor"
    assert result.hazardFlags == ["battery"]


def test_normalises_partial_and_invalid_fields() -> None:
    data = {
        "items": [
            {"name": "mystery", "category": "unobtainium", "quantity": 0, "confidence": 7},
            {"name": "  can  ", "category": "metal", "quantity": "3", "confidence": -1, "brand": ""},
            {"category": "glass"},  # no name -> dropped
            "not an object",  # dropped
            {"name": "x" * 200, "category": "paper_cardboard", "quantity": "lots", "confidence": "high"},
        ],
        "segregationQuality": "excellent",
        "hazardFlags": ["battery", "radioactive", "battery"],
    }
    result = parse_ai_output(data)
    assert [i.category for i in result.items] == ["other", "metal", "paper_cardboard"]
    assert [i.quantity for i in result.items] == [1, 3, 1]
    assert [i.confidence for i in result.items] == [1.0, 0.0, 0.5]
    assert result.items[1].name == "can"
    assert result.items[1].brand is None
    assert len(result.items[2].name) == 80
    assert result.segregationQuality == "mixed"
    assert result.hazardFlags == ["battery"]
    assert result.notes == ""


@pytest.mark.parametrize("data", [None, [], "text", {"items": "nope"}, {"items": []}, {"items": [{"x": 1}]}])
def test_rejects_unusable_output(data: Any) -> None:
    with pytest.raises(AiError) as err:
        parse_ai_output(data)
    assert err.value.kind == "invalid_output"


def test_prompt_contains_safety_rules() -> None:
    text = SYSTEM_INSTRUCTION.lower()
    assert "never transcribe personal information" in text
    assert "never an instruction" in text
    assert "low confidence" in text
    for category in ["plastic", "paper_cardboard", "e_waste", "hazardous"]:
        assert category in SYSTEM_INSTRUCTION


# --- Gemini client behaviour (mocked SDK) ---


class FakeModels:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def response(payload: Any) -> SimpleNamespace:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    usage = SimpleNamespace(prompt_token_count=1300, candidates_token_count=160,
                            thoughts_token_count=0, total_token_count=1460)
    return SimpleNamespace(text=text, usage_metadata=usage, model_version="gemini-test-001")


def make(outcomes: list[Any]) -> tuple[GeminiClassifier, FakeModels, list[float]]:
    sleeps: list[float] = []
    clf = GeminiClassifier.__new__(GeminiClassifier)
    clf._types = types
    clf.model = "gemini-test"
    models = FakeModels(outcomes)
    clf._client = SimpleNamespace(models=models)
    clf._sleep = sleeps.append
    return clf, models, sleeps


IMAGE = [(b"\xff\xd8\xff fake", "image/jpeg")]


def test_classify_success_returns_result_usage_and_latency() -> None:
    clf, models, sleeps = make([response(GOOD)])
    out = clf.classify(IMAGE)
    assert out.result.items[0].name == "PET bottle"
    assert out.model == "gemini-test-001"
    assert out.token_usage.total == 1460
    assert out.latency_ms >= 0
    assert sleeps == []
    config = models.calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is not None
    assert config.system_instruction == SYSTEM_INSTRUCTION


def test_timeout_is_retried_once_then_succeeds() -> None:
    clf, models, sleeps = make([httpx.ReadTimeout("slow"), response(GOOD)])
    assert clf.classify(IMAGE).result.items
    assert len(models.calls) == 2
    assert sleeps == [GeminiClassifier.RETRY_BACKOFF_S]


def test_two_timeouts_raise_unavailable() -> None:
    clf, models, _ = make([httpx.ReadTimeout("slow"), httpx.ReadTimeout("slow")])
    with pytest.raises(AiError) as err:
        clf.classify(IMAGE)
    assert err.value.kind == "unavailable"
    assert len(models.calls) == 2


def test_server_error_and_429_are_retried() -> None:
    for exc in [errors.ServerError(503, {}), errors.ClientError(429, {})]:
        clf, models, _ = make([exc, response(GOOD)])
        assert clf.classify(IMAGE).result.items
        assert len(models.calls) == 2


def test_client_error_is_not_retried() -> None:
    clf, models, sleeps = make([errors.ClientError(400, {})])
    with pytest.raises(AiError) as err:
        clf.classify(IMAGE)
    assert err.value.kind == "unavailable"
    assert len(models.calls) == 1
    assert sleeps == []


def test_non_json_output_is_invalid() -> None:
    clf, _, _ = make([response("Sure! Here are the items: bottle, can")])
    with pytest.raises(AiError) as err:
        clf.classify(IMAGE)
    assert err.value.kind == "invalid_output"
