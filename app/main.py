import os
from datetime import datetime, timezone

from fastapi import Depends, FastAPI

from .auth import require_shared_secret
from .chart import compute_natal
from .schemas import NatalRequest, NatalResponse


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
    return compute_natal(req)
