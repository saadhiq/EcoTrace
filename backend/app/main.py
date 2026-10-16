"""EcoTrace backend API (FastAPI on Cloud Run)."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import allowed_origins, demo_rate_limit
from app.errors import DomainError
from app.ratelimit import RateLimiter
from app.routes import auth, collector, resident

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    app = FastAPI(title="EcoTrace API", version="0.3.0")
    app.state.demo_limiter = RateLimiter(limit=demo_rate_limit(), window_seconds=60)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(DomainError)
    def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail})

    @app.get("/health")
    def health() -> dict[str, str]:
        """Liveness check used by Cloud Run and the frontend status badge."""
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(resident.router)
    app.include_router(collector.router)
    return app


app = create_app()
