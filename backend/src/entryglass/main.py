"""ASGI application entry point. Business features are intentionally absent."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from entryglass import __version__
from entryglass.api.routes.health import router as health_router
from entryglass.core.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application with injectable configuration for tests."""
    config = settings if settings is not None else Settings()
    application = FastAPI(
        title="Entryglass API",
        version=__version__,
        description=(
            "Initial scaffold only. Historical audits, replay, patterns, and preflight "
            "are planned, not implemented. No external data is queried."
        ),
    )
    application.state.settings = config
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
    )
    application.include_router(health_router, prefix="/api/v1")
    return application


app = create_app()
