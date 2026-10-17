"""users/{uid} documents in Firestore (a mirror of the role claim plus profile)."""

from typing import Protocol

from google.cloud.firestore import SERVER_TIMESTAMP, FieldFilter

from app.firebase import firestore_client
from app.models import Role, UserProfile

COLLECTION = "users"


class UserStore(Protocol):
    def get(self, uid: str) -> UserProfile | None: ...

    def upsert(self, uid: str, name: str, email: str | None, role: Role) -> UserProfile: ...

    def set_zones(self, uid: str, zones: list[str]) -> None:
        """Collectors: the zones they cover."""
        ...

    def list_by_role(self, role: Role) -> list[UserProfile]: ...

    def count_by_role(self, role: Role) -> int: ...

    def save(self, profile: UserProfile) -> None: ...


class FirestoreUserStore:
    def __init__(self) -> None:
        self._collection = firestore_client().collection(COLLECTION)

    def get(self, uid: str) -> UserProfile | None:
        snapshot = self._collection.document(uid).get()
        if not snapshot.exists:
            return None
        return UserProfile(uid=uid, **snapshot.to_dict())

    def upsert(self, uid: str, name: str, email: str | None, role: Role) -> UserProfile:
        ref = self._collection.document(uid)
        data: dict[str, object] = {"name": name, "email": email, "role": role.value}
        if not ref.get().exists:
            data["createdAt"] = SERVER_TIMESTAMP
        ref.set(data, merge=True)
        profile = self.get(uid)
        assert profile is not None
        return profile

    def set_zones(self, uid: str, zones: list[str]) -> None:
        self._collection.document(uid).set({"zones": zones}, merge=True)

    def list_by_role(self, role: Role) -> list[UserProfile]:
        query = self._collection.where(filter=FieldFilter("role", "==", role.value))
        return [UserProfile(uid=s.id, **s.to_dict()) for s in query.stream()]

    def count_by_role(self, role: Role) -> int:
        query = self._collection.where(filter=FieldFilter("role", "==", role.value))
        return int(query.count(alias="n").get()[0][0].value)

    def save(self, profile: UserProfile) -> None:
        data = profile.model_dump(mode="python", exclude={"uid"})
        if data.get("createdAt") is None:
            data["createdAt"] = SERVER_TIMESTAMP
        self._collection.document(profile.uid).set(data, merge=True)
