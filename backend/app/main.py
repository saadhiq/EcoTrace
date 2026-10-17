"""EcoTrace backend API (FastAPI on Cloud Run)."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import allowed_origins, analyze_rate_limit, demo_rate_limit, partner_rate_limit, tips_rate_limit
from app.errors import DomainError
from app.ratelimit import RateLimiter
from app.routes import auth, collector, meta, operator, partner, resident, residents

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    app = FastAPI(
        title="EcoTrace API",
        version="0.6.0",
        description=(
            "Traceable household waste collection on Google Cloud. **Partners:** see *Partner API v1* below "
            "(authenticate with **Authorize** → `X-API-Key`). The other groups are the app's own endpoints "
            "(Firebase ID token)."
        ),
        openapi_tags=[
            {"name": partner.TAG, "description": partner.TAG_DESCRIPTION},
            {"name": "App", "description": "Endpoints used by the EcoTrace web app (Firebase ID token)."},
        ],
        swagger_ui_parameters={"persistAuthorization": True, "defaultModelsExpandDepth": 0},
    )
    app.state.demo_limiter = RateLimiter(limit=demo_rate_limit(), window_seconds=60)
    app.state.analyze_limiter = RateLimiter(limit=analyze_rate_limit(), window_seconds=60)
    app.state.tips_limiter = RateLimiter(limit=tips_rate_limit(), window_seconds=60)
    app.state.partner_limiter = RateLimiter(limit=partner_rate_limit(), window_seconds=60)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_methods=["GET", "POST", "PATCH", "PUT"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(DomainError)
    def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail})

    @app.get("/health", tags=["App"])
    def health() -> dict[str, str]:
        """Liveness check used by Cloud Run and the frontend status badge."""
        return {"status": "ok"}

    app.include_router(partner.router)  # listed first in /docs
    app.include_router(meta.router, tags=["App"])
    app.include_router(auth.router, tags=["App"])
    app.include_router(resident.router, tags=["App"])
    app.include_router(collector.router, tags=["App"])
    app.include_router(operator.router, tags=["App"])
    app.include_router(residents.router, tags=["App"])
    return app


app = create_app()
