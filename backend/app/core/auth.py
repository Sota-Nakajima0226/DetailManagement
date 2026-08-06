"""Supabase Auth 連携。

Supabase Auth の access token をローカル検証する。
- JWT Signing Keys（ES256 / RS256 など）: Project URL の JWKS で公開鍵検証
- Legacy JWT Secret（HS256）: 後方互換（任意）

検証後、JWT の sub（UUID）で `users` テーブルを引き、登録済みユーザーのみ通す。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt
from sqlalchemy.orm import Session

from app.core.config import (
    SUPABASE_JWT_ALGORITHMS_LEGACY,
    SUPABASE_JWT_ALGORITHMS_ASYMMETRIC,
    SUPABASE_JWT_AUDIENCE,
    SUPABASE_JWT_SECRET,
    SUPABASE_URL,
)
from app.core.database import get_db
from app.models import User


logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

_JWKS_CACHE_TTL_SECONDS = 600
_jwks_cache: Optional[dict[str, Any]] = None
_jwks_cache_fetched_at: float = 0.0


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _auth_not_configured() -> HTTPException:
    logger.error("Supabase auth is not configured (SUPABASE_URL and/or SUPABASE_JWT_SECRET)")
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Authentication is not configured on the server",
    )


def _jwks_url() -> str:
    return f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"


def _fetch_jwks() -> dict[str, Any]:
    global _jwks_cache, _jwks_cache_fetched_at

    now = time.time()
    if _jwks_cache is not None and now - _jwks_cache_fetched_at < _JWKS_CACHE_TTL_SECONDS:
        return _jwks_cache

    try:
        with urlopen(_jwks_url(), timeout=10) as response:
            jwks = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to fetch JWKS from Supabase: %s", exc)
        raise _unauthorized("Unable to verify token signing keys") from exc

    if not isinstance(jwks, dict) or "keys" not in jwks:
        logger.error("Invalid JWKS payload from Supabase")
        raise _unauthorized("Unable to verify token signing keys")

    _jwks_cache = jwks
    _jwks_cache_fetched_at = now
    return jwks


def _signing_key_from_jwks(token: str, header: dict[str, Any]) -> Any:
    kid = header.get("kid")
    if not kid:
        raise JWTError("Token header has no kid")

    jwks = _fetch_jwks()
    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            return jwk.construct(key_data)

    # kid がローテーション直後などでキャッシュに無い場合は 1 回だけ再取得
    global _jwks_cache
    _jwks_cache = None
    jwks = _fetch_jwks()
    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            return jwk.construct(key_data)

    raise JWTError(f"Signing key not found for kid={kid}")


def decode_access_token(token: str) -> dict[str, Any]:
    """Supabase access token を検証し、JWT ペイロードを返す。"""
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise _unauthorized("Invalid or expired token") from exc

    alg = header.get("alg")
    if not alg:
        raise _unauthorized("Invalid or expired token")

    decode_options = {"verify_aud": True}
    issuer = f"{SUPABASE_URL.rstrip('/')}/auth/v1" if SUPABASE_URL else None
    if issuer:
        decode_options["verify_iss"] = True

    try:
        if alg == "HS256":
            if not SUPABASE_JWT_SECRET:
                raise _auth_not_configured()
            return jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=list(SUPABASE_JWT_ALGORITHMS_LEGACY),
                audience=SUPABASE_JWT_AUDIENCE,
                issuer=issuer,
                options=decode_options,
            )

        if alg not in SUPABASE_JWT_ALGORITHMS_ASYMMETRIC:
            raise JWTError(f"Algorithm {alg} is not allowed")

        if not SUPABASE_URL:
            raise _auth_not_configured()

        key = _signing_key_from_jwks(token, header)
        return jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience=SUPABASE_JWT_AUDIENCE,
            issuer=issuer,
            options=decode_options,
        )
    except HTTPException:
        raise
    except JWTError as exc:
        logger.info("JWT verification failed: %s", exc)
        raise _unauthorized("Invalid or expired token") from exc


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Authorization: Bearer の JWT を検証し、`users` の行を返す。"""
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Authorization header is missing")

    payload = decode_access_token(credentials.credentials)

    subject = payload.get("sub")
    if not subject:
        raise _unauthorized("Token has no subject")

    user = db.get(User, str(subject))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not registered for this app",
        )
    return user
