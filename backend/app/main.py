"""EcoTrace backend API (FastAPI on Cloud Run)."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import allowed_origins, demo_rate_limit
from app.ratelimit import RateLimiter
from app.routes import auth

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    app = FastAPI(title="EcoTrace API", version="0.1.0")
    app.state.demo_limiter = RateLimiter(limit=demo_rate_limit(), window_seconds=60)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Liveness check used by Cloud Run and the frontend status badge."""
        return {"status": "ok"}

    app.include_router(auth.router)
    return app


app = create_app()
