"""Shared domain models."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class Role(StrEnum):
    RESIDENT = "resident"
    COLLECTOR = "collector"
    OPERATOR = "operator"
    ADMIN = "admin"


class CurrentUser(BaseModel):
    """The caller, as described by a verified Firebase ID token."""

    uid: str
    email: str | None = None
    name: str | None = None
    role: Role | None = None


class UserProfile(BaseModel):
    """Mirror of users/{uid} in Firestore."""

    uid: str
    name: str
    email: str | None = None
    role: Role
    createdAt: datetime | None = None
