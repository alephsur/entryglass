"""ASGI entry point for the local-first review and replay application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from entryglass import __version__
from entryglass.api.routes.health import router as health_router
from entryglass.api.routes.precedents import router as precedents_router
from entryglass.api.routes.reviews import router as reviews_router
from entryglass.core.config import Settings
from entryglass.infrastructure.preflight_service import PreflightService
from entryglass.infrastructure.review_service import ReviewService
from entryglass.infrastructure.storage import SqliteIngestionRepository


def create_app(
    settings: Settings | None = None,
    *,
    repository: SqliteIngestionRepository | None = None,
    review_service: ReviewService | None = None,
    preflight_service: PreflightService | None = None,
) -> FastAPI:
    """Build the application with injectable configuration for tests."""
    config = settings if settings is not None else Settings()
    application = FastAPI(
        title="Entryglass API",
        version=__version__,
        description=(
            "Local-first wallet-entry review with strictly pre-entry context, separately "
            "revealed later price observations, inspectable evidence, descriptive "
            "personal precedents, and current-token comparison."
        ),
    )
    storage = repository or SqliteIngestionRepository(config.database_path)
    application.state.settings = config
    application.state.review_repository = storage
    application.state.review_service = review_service or ReviewService(config, storage)
    application.state.preflight_service = preflight_service or PreflightService(config, storage)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
    )
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(reviews_router, prefix="/api/v1")
    application.include_router(precedents_router, prefix="/api/v1")
    return application


app = create_app()
