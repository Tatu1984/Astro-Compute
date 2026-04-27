import logging
import os
import traceback
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, status

from .auth import require_shared_secret
from .chart import compute_natal
from .schemas import NatalRequest, NatalResponse


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
