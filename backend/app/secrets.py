"""Read the DEMO partner API keys from Secret Manager (nothing else).

The backend's service account has secretAccessor on exactly these two secrets
(per-secret IAM bindings), so even a bug here can't read other secrets.
"""

from typing import Protocol

from app import config
from app.errors import DomainError

DEMO_PARTNER_IDS = ("greencart-lk", "ecohome-store")


def demo_secret_id(partner_id: str) -> str:
    return f"partner-api-key-{partner_id}"


class DemoKeyReader(Protocol):
    def read(self, partner_id: str) -> str: ...


class SecretManagerDemoKeyReader:
    def __init__(self) -> None:
        from google.cloud import secretmanager

        self._client = secretmanager.SecretManagerServiceClient()

    def read(self, partner_id: str) -> str:
        if partner_id not in DEMO_PARTNER_IDS:
            raise DomainError(404, "not_a_demo_partner")
        name = f"projects/{config.project_id()}/secrets/{demo_secret_id(partner_id)}/versions/latest"
        return self._client.access_secret_version(name=name).payload.data.decode()
