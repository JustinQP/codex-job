from __future__ import annotations

import os

from fastapi import Header, HTTPException, status


def require_api_token(x_api_token: str | None = Header(default=None)) -> None:
    expected = os.environ.get("API_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API token is not configured",
        )
    agent_token = os.environ.get("AGENT_TOKEN")
    if agent_token and agent_token == expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API token and agent token must be distinct",
        )
    if x_api_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid API token",
        )


def require_agent_token(x_agent_token: str | None = Header(default=None)) -> None:
    expected = os.environ.get("AGENT_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="agent token is not configured",
        )
    api_token = os.environ.get("API_TOKEN")
    if api_token and api_token == expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API token and agent token must be distinct",
        )
    if x_agent_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid agent token",
        )
