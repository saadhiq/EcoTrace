"""EcoTrace backend API (FastAPI on Cloud Run)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import allowed_origins


def create_app() -> FastAPI:
    app = FastAPI(title="EcoTrace API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_methods=["GET"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Liveness check used by Cloud Run and the frontend status badge."""
        return {"status": "ok"}

    return app


app = create_app()
