"""Firebase Admin SDK setup, using Application Default Credentials.

On Cloud Run the credentials are the runtime service account (no key file).
"""

from functools import lru_cache

import firebase_admin
from google.cloud.firestore import Client as FirestoreClient

from app.config import project_id


@lru_cache
def firebase_app() -> firebase_admin.App:
    options = {"projectId": pid} if (pid := project_id()) else None
    return firebase_admin.initialize_app(options=options)


@lru_cache
def firestore_client() -> FirestoreClient:
    from firebase_admin import firestore

    return firestore.client(app=firebase_app())
