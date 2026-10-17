"""Firestore access for households, bags and pickups, behind a small interface.

No transactions (demo scope): uniqueness uses `create()` (fails if the doc
exists) and multi-document updates go through one atomic batch write.
"""

from typing import Protocol

from google.api_core.exceptions import AlreadyExists, Conflict
from google.cloud.firestore import FieldFilter

from app.firebase import firestore_client
from app.models import (
    Bag,
    BagStatus,
    ConsentEntry,
    Household,
    HouseholdStats,
    LedgerEntry,
    Pickup,
    PickupStatus,
    RouteStop,
    TipsCache,
    WasteRecord,
    WasteRecordStatus,
    to_doc,
)

HOUSEHOLDS = "households"
BAGS = "bags"
PICKUPS = "pickups"
ROUTES = "routes"
WASTE_RECORDS = "wasteRecords"
# Subcollections of households/{id}
STATS, STATS_DOC = "stats", "summary"
LEDGER = "pointsLedger"
TIPS = "tips"
CONSENT_HISTORY = "consentHistory"


class DataStore(Protocol):
    def create_household(self, household: Household) -> bool:
        """False if the household already exists."""
        ...

    def get_household(self, household_id: str) -> Household | None: ...

    def get_households(self, household_ids: list[str]) -> dict[str, Household]: ...

    def save_household(self, household: Household) -> None: ...

    def create_bags(self, bags: list[Bag]) -> bool:
        """All-or-nothing; False if any code is already taken."""
        ...

    def get_bags(self, codes: list[str]) -> dict[str, Bag]: ...

    def list_bags(self, household_id: str) -> list[Bag]: ...

    def list_bags_by_status(self, status: BagStatus) -> list[Bag]: ...

    def get_waste_records(self, codes: list[str]) -> dict[str, WasteRecord]: ...

    def list_confirmed_records(self, household_id: str) -> list[WasteRecord]: ...

    def get_pickups(self, pickup_ids: list[str]) -> dict[str, Pickup]: ...

    def get_stats(self, household_id: str) -> HouseholdStats | None: ...

    def get_tips(self, household_id: str, lang: str) -> TipsCache | None: ...

    def save_tips(self, household_id: str, cache: TipsCache) -> None: ...

    def list_consent_history(self, household_id: str, limit: int = 10) -> list[ConsentEntry]: ...

    def save_waste_record(self, record: WasteRecord) -> None:
        """Write a draft record (analysis before confirmation)."""
        ...

    def get_pickup(self, pickup_id: str) -> Pickup | None: ...

    def list_pickups(self, household_id: str) -> list[Pickup]: ...

    def list_requested_pickups(self, zones: list[str], day: str) -> list[Pickup]:
        """Unassigned (`requested`) pickups on `day` in any of `zones`."""
        ...

    def list_collector_pickups(
        self, collector_uid: str, *, day: str | None = None, status: PickupStatus | None = None
    ) -> list[Pickup]: ...

    def new_pickup_id(self) -> str: ...

    def commit(
        self,
        pickups: list[Pickup],
        bags: list[Bag],
        routes: list[RouteStop] | None = None,
        records: list[WasteRecord] | None = None,
        *,
        households: list[Household] | None = None,
        stats: list[tuple[str, HouseholdStats]] | None = None,
        ledger: list[tuple[str, LedgerEntry]] | None = None,
        consent: list[tuple[str, ConsentEntry]] | None = None,
    ) -> None:
        """Write all given documents in one atomic batch."""
        ...


class FirestoreDataStore:
    def __init__(self) -> None:
        self._db = firestore_client()

    def _households(self):  # noqa: ANN202
        return self._db.collection(HOUSEHOLDS)

    def _bags(self):  # noqa: ANN202
        return self._db.collection(BAGS)

    def _pickups(self):  # noqa: ANN202
        return self._db.collection(PICKUPS)

    def _routes(self):  # noqa: ANN202
        return self._db.collection(ROUTES)

    def _records(self):  # noqa: ANN202
        return self._db.collection(WASTE_RECORDS)

    # --- households ---
    def create_household(self, household: Household) -> bool:
        try:
            self._households().document(household.id).create(to_doc(household, "id"))
        except (AlreadyExists, Conflict):
            return False
        return True

    def get_household(self, household_id: str) -> Household | None:
        snap = self._households().document(household_id).get()
        return Household(id=snap.id, **snap.to_dict()) if snap.exists else None

    def get_households(self, household_ids: list[str]) -> dict[str, Household]:
        refs = [self._households().document(hid) for hid in dict.fromkeys(household_ids)]
        return {
            snap.id: Household(id=snap.id, **snap.to_dict())
            for snap in self._db.get_all(refs)
            if snap.exists
        }

    def save_household(self, household: Household) -> None:
        self._households().document(household.id).set(to_doc(household, "id"))

    # --- bags ---
    def create_bags(self, bags: list[Bag]) -> bool:
        batch = self._db.batch()
        for bag in bags:
            batch.create(self._bags().document(bag.code), to_doc(bag, "code"))
        try:
            batch.commit()
        except (AlreadyExists, Conflict):
            return False
        return True

    def get_bags(self, codes: list[str]) -> dict[str, Bag]:
        refs = [self._bags().document(code) for code in codes]
        return {
            snap.id: Bag(code=snap.id, **snap.to_dict())
            for snap in self._db.get_all(refs)
            if snap.exists
        }

    def list_bags(self, household_id: str) -> list[Bag]:
        query = self._bags().where(filter=FieldFilter("householdId", "==", household_id))
        bags = [Bag(code=snap.id, **snap.to_dict()) for snap in query.stream()]
        return sorted(bags, key=lambda bag: (bag.issuedAt, bag.code))

    def list_bags_by_status(self, status: BagStatus) -> list[Bag]:
        query = self._bags().where(filter=FieldFilter("status", "==", status.value))
        return [Bag(code=snap.id, **snap.to_dict()) for snap in query.stream()]

    # --- waste records ---
    def get_waste_records(self, codes: list[str]) -> dict[str, WasteRecord]:
        refs = [self._records().document(code) for code in dict.fromkeys(codes)]
        return {
            snap.id: WasteRecord(bagCode=snap.id, **snap.to_dict())
            for snap in self._db.get_all(refs)
            if snap.exists
        }

    def save_waste_record(self, record: WasteRecord) -> None:
        self._records().document(record.bagCode).set(to_doc(record, "bagCode"))

    def list_confirmed_records(self, household_id: str) -> list[WasteRecord]:
        query = (
            self._records()
            .where(filter=FieldFilter("householdId", "==", household_id))
            .where(filter=FieldFilter("status", "==", WasteRecordStatus.CONFIRMED.value))
        )
        return [WasteRecord(bagCode=snap.id, **snap.to_dict()) for snap in query.stream()]

    # --- household subcollections ---
    def _sub(self, household_id: str, name: str):  # noqa: ANN202
        return self._households().document(household_id).collection(name)

    def get_stats(self, household_id: str) -> HouseholdStats | None:
        snap = self._sub(household_id, STATS).document(STATS_DOC).get()
        return HouseholdStats(**snap.to_dict()) if snap.exists else None

    def get_tips(self, household_id: str, lang: str) -> TipsCache | None:
        snap = self._sub(household_id, TIPS).document(lang).get()
        return TipsCache(**snap.to_dict()) if snap.exists else None

    def save_tips(self, household_id: str, cache: TipsCache) -> None:
        self._sub(household_id, TIPS).document(cache.lang).set(cache.model_dump(mode="python"))

    def list_consent_history(self, household_id: str, limit: int = 10) -> list[ConsentEntry]:
        query = self._sub(household_id, CONSENT_HISTORY).order_by("at", direction="DESCENDING").limit(limit)
        return [ConsentEntry(**snap.to_dict()) for snap in query.stream()]

    # --- pickups ---
    def get_pickups(self, pickup_ids: list[str]) -> dict[str, Pickup]:
        refs = [self._pickups().document(pid) for pid in dict.fromkeys(pickup_ids)]
        return {
            snap.id: Pickup(id=snap.id, **snap.to_dict())
            for snap in self._db.get_all(refs)
            if snap.exists
        }

    def get_pickup(self, pickup_id: str) -> Pickup | None:
        snap = self._pickups().document(pickup_id).get()
        return Pickup(id=snap.id, **snap.to_dict()) if snap.exists else None

    def list_pickups(self, household_id: str) -> list[Pickup]:
        query = self._pickups().where(filter=FieldFilter("householdId", "==", household_id))
        pickups = [Pickup(id=snap.id, **snap.to_dict()) for snap in query.stream()]
        return sorted(pickups, key=lambda p: (p.date, p.createdAt), reverse=True)

    def list_requested_pickups(self, zones: list[str], day: str) -> list[Pickup]:
        if not zones:
            return []
        query = (
            self._pickups()
            .where(filter=FieldFilter("zone", "in", zones[:30]))
            .where(filter=FieldFilter("date", "==", day))
            .where(filter=FieldFilter("status", "==", PickupStatus.REQUESTED.value))
        )
        return [Pickup(id=snap.id, **snap.to_dict()) for snap in query.stream()]

    def list_collector_pickups(
        self, collector_uid: str, *, day: str | None = None, status: PickupStatus | None = None
    ) -> list[Pickup]:
        query = self._pickups().where(filter=FieldFilter("collectorUid", "==", collector_uid))
        if day is not None:
            query = query.where(filter=FieldFilter("date", "==", day))
        if status is not None:
            query = query.where(filter=FieldFilter("status", "==", status.value))
        return [Pickup(id=snap.id, **snap.to_dict()) for snap in query.stream()]

    def new_pickup_id(self) -> str:
        return self._pickups().document().id

    # --- batch ---
    def commit(
        self,
        pickups: list[Pickup],
        bags: list[Bag],
        routes: list[RouteStop] | None = None,
        records: list[WasteRecord] | None = None,
        *,
        households: list[Household] | None = None,
        stats: list[tuple[str, HouseholdStats]] | None = None,
        ledger: list[tuple[str, LedgerEntry]] | None = None,
        consent: list[tuple[str, ConsentEntry]] | None = None,
    ) -> None:
        batch = self._db.batch()
        for household in households or []:
            batch.set(self._households().document(household.id), to_doc(household, "id"))
        for household_id, summary in stats or []:
            batch.set(self._sub(household_id, STATS).document(STATS_DOC), summary.model_dump(mode="python"))
        for household_id, entry in ledger or []:
            batch.set(self._sub(household_id, LEDGER).document(entry.id), to_doc(entry, "id"))
        for household_id, entry in consent or []:
            batch.set(self._sub(household_id, CONSENT_HISTORY).document(), entry.model_dump(mode="python"))
        for pickup in pickups:
            batch.set(self._pickups().document(pickup.id), to_doc(pickup, "id"))
        for bag in bags:
            batch.set(self._bags().document(bag.code), to_doc(bag, "code"))
        for route in routes or []:
            batch.set(self._routes().document(route.pickupId), to_doc(route, "pickupId"))
        for record in records or []:
            batch.set(self._records().document(record.bagCode), to_doc(record, "bagCode"))
        batch.commit()
