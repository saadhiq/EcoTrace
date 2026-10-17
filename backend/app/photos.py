"""Bag photos: validation and private Cloud Storage upload.

The bucket is private (public access prevention), deletes objects after 30
days (lifecycle rule), and the backend can only create and read objects.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app import config
from app.errors import DomainError

MAX_PHOTOS = 3
MAX_PHOTO_BYTES = 4 * 1024 * 1024


@dataclass
class Photo:
    data: bytes
    mime: str


def sniff_mime(data: bytes) -> str | None:
    """Detect JPEG/PNG/WebP from the file header (don't trust the client)."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_photos(blobs: list[bytes]) -> list[Photo]:
    if not 1 <= len(blobs) <= MAX_PHOTOS:
        raise DomainError(422, "photo_count")
    photos = []
    for data in blobs:
        if len(data) > MAX_PHOTO_BYTES:
            raise DomainError(413, "photo_too_large")
        mime = sniff_mime(data)
        if mime is None:
            raise DomainError(415, "unsupported_photo_type")
        photos.append(Photo(data=data, mime=mime))
    return photos


class PhotoStore(Protocol):
    def save(self, bag_code: str, photos: list[Photo], now: datetime) -> list[str]:
        """Store photos; returns gs:// paths."""
        ...


EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class GcsPhotoStore:
    def __init__(self) -> None:
        from google.cloud import storage

        self._bucket = storage.Client(project=config.project_id()).bucket(config.photo_bucket())

    def save(self, bag_code: str, photos: list[Photo], now: datetime) -> list[str]:
        stamp = now.strftime("%Y%m%dT%H%M%S%f")
        paths = []
        for i, photo in enumerate(photos, start=1):
            name = f"bags/{bag_code}/{stamp}-{i}.{EXTENSIONS[photo.mime]}"
            blob = self._bucket.blob(name)
            # if_generation_match=0: create only, never overwrite (objectCreator).
            blob.upload_from_string(photo.data, content_type=photo.mime, if_generation_match=0)
            paths.append(f"gs://{self._bucket.name}/{name}")
        return paths
