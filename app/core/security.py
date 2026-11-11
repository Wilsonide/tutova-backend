import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _password_hasher.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def create_access_token(subject: str, role: str) -> str:
    now = datetime.now(UTC)

    payload = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )

    if payload.get("type") != "access" or not payload.get("sub"):
        raise jwt.InvalidTokenError("Invalid access token")

    return payload


def new_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
