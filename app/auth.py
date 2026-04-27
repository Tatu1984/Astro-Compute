import os

from fastapi import Header, HTTPException, status

SECRET_HEADER = "X-Compute-Secret"


def require_shared_secret(x_compute_secret: str | None = Header(default=None)) -> None:
    expected = os.getenv("COMPUTE_SHARED_SECRET")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="COMPUTE_SHARED_SECRET not configured on server",
        )
    if x_compute_secret != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing shared secret",
        )
