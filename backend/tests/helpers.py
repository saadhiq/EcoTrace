from typing import Any

from fastapi.testclient import TestClient

from tests.fakes import FakeIdentity

HOUSEHOLD = {
    "name": "Silva Household",
    "phone": "+94 71 555 0101",
    "addressLine": "45 Lake Drive",
    "zone": "colombo-05",
}


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def resident(identity: FakeIdentity, uid: str = "res-1") -> dict[str, str]:
    identity.issue(f"tok-{uid}", uid, role="resident")
    return auth(f"tok-{uid}")


def onboard(client: TestClient, identity: FakeIdentity, uid: str = "res-1") -> dict[str, Any]:
    headers = resident(identity, uid)
    response = client.post("/households", json=HOUSEHOLD, headers=headers)
    assert response.status_code == 201, response.text
    return {"headers": headers, **response.json()}
