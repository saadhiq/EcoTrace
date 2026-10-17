"""Warehouse operator endpoints: queue, bag, analyze (Gemini), confirm."""

from functools import lru_cache

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app import operator
from app.ai.classifier import Classifier, GeminiClassifier
from app.auth import require_role
from app.clock import Clock
from app.deps import get_clock, get_store
from app.errors import DomainError
from app.models import CurrentUser, Role
from app.photos import MAX_PHOTO_BYTES, MAX_PHOTOS, GcsPhotoStore, PhotoStore
from app.ratelimit import RateLimiter
from app.store import DataStore
from app.taxonomy import HazardFlag, SegregationQuality

router = APIRouter(prefix="/operator")
operator_only = require_role(Role.OPERATOR)


@lru_cache
def _classifier() -> GeminiClassifier:
    return GeminiClassifier()


def get_classifier() -> Classifier:
    return _classifier()


@lru_cache
def _photo_store() -> GcsPhotoStore:
    return GcsPhotoStore()


def get_photo_store() -> PhotoStore:
    return _photo_store()


def get_analyze_limiter(request: Request) -> RateLimiter:
    return request.app.state.analyze_limiter


class ConfirmRequest(BaseModel):
    finalItems: list[operator.FinalItem] = Field(min_length=1, max_length=50)
    segregationQuality: SegregationQuality
    hazardFlags: list[HazardFlag] = Field(default_factory=list, max_length=6)


@router.get("/queue", response_model=list[operator.QueueItem])
def queue(
    _: CurrentUser = Depends(operator_only), store: DataStore = Depends(get_store)
) -> list[operator.QueueItem]:
    return operator.queue(store)


@router.get("/bags/{code}", response_model=operator.BagView)
def bag(
    code: str, _: CurrentUser = Depends(operator_only), store: DataStore = Depends(get_store)
) -> operator.BagView:
    return operator.get_bag(store, code.strip().upper())


@router.post("/bags/{code}/analyze", response_model=operator.AnalyzeResult)
async def analyze(
    code: str,
    photos: list[UploadFile] = File(...),
    user: CurrentUser = Depends(operator_only),
    store: DataStore = Depends(get_store),
    photo_store: PhotoStore = Depends(get_photo_store),
    classifier: Classifier = Depends(get_classifier),
    clock: Clock = Depends(get_clock),
    limiter: RateLimiter = Depends(get_analyze_limiter),
) -> operator.AnalyzeResult:
    """Upload 1-3 photos and classify them with Gemini. Does NOT mark the bag processed."""
    if not limiter.allow(user.uid):
        raise DomainError(429, "rate_limited")
    if not 1 <= len(photos) <= MAX_PHOTOS:
        raise DomainError(422, "photo_count")
    blobs = []
    for upload in photos:
        data = await upload.read(MAX_PHOTO_BYTES + 1)
        blobs.append(data)
    # Gemini + Cloud Storage calls are blocking; run them off the event loop.
    return await run_in_threadpool(
        operator.analyze, store, photo_store, classifier, clock, code.strip().upper(), blobs
    )


@router.post("/bags/{code}/confirm", response_model=operator.ConfirmResult)
def confirm(
    code: str,
    body: ConfirmRequest,
    user: CurrentUser = Depends(operator_only),
    store: DataStore = Depends(get_store),
    clock: Clock = Depends(get_clock),
) -> operator.ConfirmResult:
    return operator.confirm(
        store,
        clock,
        user.uid,
        code.strip().upper(),
        body.finalItems,
        body.segregationQuality,
        body.hazardFlags,
    )
