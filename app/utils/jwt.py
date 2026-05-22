import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException, status

from app.config.settings import get_settings


settings = get_settings()


def _build_token(payload: dict[str, Any], expires_delta: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    token_payload = {
        **payload,
        "type": token_type,
        "jti": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(token_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(payload: dict[str, Any]) -> str:
    return _build_token(payload, timedelta(minutes=settings.jwt_expire_minutes), "access")


def create_refresh_token(payload: dict[str, Any]) -> str:
    return _build_token(payload, timedelta(days=settings.refresh_token_expire_days), "refresh")


def create_reset_token(payload: dict[str, Any]) -> str:
    return _build_token(payload, timedelta(minutes=settings.reset_token_expire_minutes), "password_reset")


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    if expected_type and payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    return payload
