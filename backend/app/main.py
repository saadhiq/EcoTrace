"""EcoTrace backend API (FastAPI on Cloud Run)."""

from fastapi import FastAPI

app = FastAPI(title="EcoTrace API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check used by Cloud Run and local smoke tests."""
    return {"status": "ok"}
