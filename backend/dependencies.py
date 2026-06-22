from __future__ import annotations

import os

from fastapi import Header, HTTPException, status


def require_api_token(x_api_token: str | None = Header(default=None)) -> None:
    expected = os.environ.get("API_TOKEN")
    if not expected:
        return
    if x_api_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid API token",
        )
