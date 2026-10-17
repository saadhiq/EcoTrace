"""Fixed waste taxonomy shared by Gemini's response schema, validation and the UI.

Served at GET /taxonomy. Change it here only.
"""

from typing import Literal, get_args

Category = Literal[
    "plastic",
    "paper_cardboard",
    "glass",
    "metal",
    "organic",
    "e_waste",
    "textile",
    "hazardous",
    "other",
]
HazardFlag = Literal["sharp", "battery", "chemical", "medical", "broken_glass", "flammable"]
SegregationQuality = Literal["good", "mixed", "poor"]

CATEGORIES: tuple[str, ...] = get_args(Category)
HAZARD_FLAGS: tuple[str, ...] = get_args(HazardFlag)
SEGREGATION_QUALITIES: tuple[str, ...] = get_args(SegregationQuality)

CATEGORY_LABELS: dict[str, str] = {
    "plastic": "Plastic",
    "paper_cardboard": "Paper & cardboard",
    "glass": "Glass",
    "metal": "Metal",
    "organic": "Organic",
    "e_waste": "E-waste",
    "textile": "Textile",
    "hazardous": "Hazardous",
    "other": "Other",
}
HAZARD_LABELS: dict[str, str] = {
    "sharp": "Sharp",
    "battery": "Battery",
    "chemical": "Chemical",
    "medical": "Medical",
    "broken_glass": "Broken glass",
    "flammable": "Flammable",
}
