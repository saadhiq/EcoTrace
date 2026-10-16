"""Firestore access for households, bags and pickups, behind a small interface.

No transactions (demo scope): uniqueness uses `create()` (fails if the doc
exists) and multi-document updates go through one atomic batch write.
"""

from typing import Protocol

from google.api_core.exceptions import AlreadyExists, Conflict
from google.cloud.firestore import FieldFilter

from app.firebase import firestore_client
from app.models import Bag, Household, Pickup, PickupStatus, RouteStop, to_doc

HOUSEHOLDS = "households"
BAGS = "bags"
PICKUPS = "pickups"
ROUTES = "routes"


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
        self, pickups: list[Pickup], bags: list[Bag], routes: list[RouteStop] | None = None
    ) -> None:
        """Write these pickups, bags and route mirrors together in one atomic batch."""
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

    # --- pickups ---
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
        self, pickups: list[Pickup], bags: list[Bag], routes: list[RouteStop] | None = None
    ) -> None:
        batch = self._db.batch()
        for pickup in pickups:
            batch.set(self._pickups().document(pickup.id), to_doc(pickup, "id"))
        for bag in bags:
            batch.set(self._bags().document(bag.code), to_doc(bag, "code"))
        for route in routes or []:
            batch.set(self._routes().document(route.pickupId), to_doc(route, "pickupId"))
        batch.commit()
