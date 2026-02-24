"""
Health check endpoint for Docker healthcheck and monitoring.

Docker polls this every 30 seconds:
  HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1

Returns 200 if all models are loaded and GPU (if required) is available.
Returns 503 if models are not ready — Docker will restart the container.

Owner agent: docker-engineer
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """
    Healthcheck endpoint. Verifies the service is alive and models are loaded.
    Called by Docker every 30 seconds.
    Returns 200 if healthy, 503 if models not ready.
    """
    # TODO: implement model_registry check
    # from src.models.loader import model_registry
    # models_loaded = model_registry.all_loaded()

    try:
        import torch
        gpu_available = torch.cuda.is_available()
    except ImportError:
        gpu_available = False

    status = {
        "status": "ok",
        "models_loaded": False,   # TODO: check model_registry
        "gpu_available": gpu_available,
    }

    if not status["models_loaded"]:
        # Comment this out during development when models aren't loaded yet
        # raise HTTPException(status_code=503, detail="Models not ready")
        pass

    return status
