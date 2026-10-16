"""Service zones (Colombo area). Single source of truth; served at GET /zones."""

from pydantic import BaseModel


class Zone(BaseModel):
    id: str
    name: str


ZONES: list[Zone] = [
    Zone(id="colombo-03", name="Colombo 03 – Kollupitiya"),
    Zone(id="colombo-05", name="Colombo 05 – Havelock Town"),
    Zone(id="colombo-07", name="Colombo 07 – Cinnamon Gardens"),
    Zone(id="dehiwala", name="Dehiwala–Mount Lavinia"),
    Zone(id="nugegoda", name="Nugegoda"),
    Zone(id="rajagiriya", name="Rajagiriya"),
]

ZONE_IDS = {zone.id for zone in ZONES}
