"""A liveness check, not a data-provider readiness check."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from entryglass import __version__

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Describe the running scaffold without claiming analytics readiness."""

    status: Literal["ok"] = "ok"
    service: str = "Entryglass API"
    version: str = __version__
    stage: Literal["scaffold"] = "scaffold"
    nansen_integration: Literal["validation_only"] = "validation_only"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return process health without network calls or API-credit consumption."""
    return HealthResponse()
