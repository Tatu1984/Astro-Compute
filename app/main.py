import logging
import os
import traceback
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, status

from .auth import require_shared_secret
from .chart import compute_natal, compute_transit
from .schemas import (
    NatalRequest,
    NatalResponse,
    TransitRequest,
    TransitResponse,
    VedicRequest,
    VedicResponse,
)
from .vedic import compute_vedic


logger = logging.getLogger("astro-compute")
logging.basicConfig(level=logging.INFO)


app = FastAPI(
    title="Astro Compute",
    version="0.1.0",
    description="Deterministic astrology compute service (Swiss Ephemeris).",
)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "ok": True,
        "service": "astro-compute",
        "now_utc": datetime.now(timezone.utc).isoformat(),
        "secret_configured": bool(os.getenv("COMPUTE_SHARED_SECRET")),
    }


@app.post(
    "/natal",
    response_model=NatalResponse,
    dependencies=[Depends(require_shared_secret)],
)
def natal(req: NatalRequest) -> NatalResponse:
    try:
        return compute_natal(req)
    except Exception as exc:
        logger.error("natal compute failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"compute error: {type(exc).__name__}: {exc}",
        ) from exc


@app.post(
    "/transit",
    response_model=TransitResponse,
    dependencies=[Depends(require_shared_secret)],
)
def transit(req: TransitRequest) -> TransitResponse:
    try:
        return compute_transit(req)
    except Exception as exc:
        logger.error("transit compute failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"compute error: {type(exc).__name__}: {exc}",
        ) from exc


@app.post(
    "/vedic",
    response_model=VedicResponse,
    dependencies=[Depends(require_shared_secret)],
)
def vedic(req: VedicRequest) -> VedicResponse:
    try:
        return compute_vedic(req)
    except Exception as exc:
        logger.error("vedic compute failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"compute error: {type(exc).__name__}: {exc}",
        ) from exc
