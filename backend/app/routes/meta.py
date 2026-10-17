"""Public reference data: service zones and the waste taxonomy."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.taxonomy import CATEGORIES, CATEGORY_LABELS, HAZARD_FLAGS, HAZARD_LABELS, SEGREGATION_QUALITIES
from app.zones import ZONES, Zone

router = APIRouter()


class Option(BaseModel):
    id: str
    label: str


class Taxonomy(BaseModel):
    categories: list[Option]
    hazardFlags: list[Option]
    segregationQualities: list[str]


@router.get("/zones", response_model=list[Zone])
def zones() -> list[Zone]:
    return ZONES


@router.get("/taxonomy", response_model=Taxonomy)
def taxonomy() -> Taxonomy:
    return Taxonomy(
        categories=[Option(id=c, label=CATEGORY_LABELS[c]) for c in CATEGORIES],
        hazardFlags=[Option(id=h, label=HAZARD_LABELS[h]) for h in HAZARD_FLAGS],
        segregationQualities=list(SEGREGATION_QUALITIES),
    )
