"""Password hashes (Argon2) and login tokens (JWT). The only module that imports pwdlib and jwt."""

import asyncio
import datetime as dt
import uuid

import jwt
from pwdlib import PasswordHash

ALGORITHM = "HS256"

_hasher = PasswordHash.recommended()  # Argon2id with the library's current parameters

# Checked when the email is unknown, so a failed login takes as long with an unknown email as
# with a wrong password, and the response time does not reveal who has an account.
_DUMMY_HASH = _hasher.hash("not a real password")


async def hash_password(password: str) -> str:
    # Argon2 is slow on purpose (~50 ms of CPU): in a thread, so other requests keep running.
    return await asyncio.to_thread(_hasher.hash, password)


async def verify_password(password: str, password_hash: str | None) -> bool:
    """False for a wrong password, and for `None` (no such user) after the same amount of work."""
    matches = await asyncio.to_thread(_hasher.verify, password, password_hash or _DUMMY_HASH)
    return matches and password_hash is not None


def create_token(user_id: uuid.UUID, secret: str, ttl_minutes: int) -> str:
    now = dt.datetime.now(dt.UTC)
    claims = {"sub": str(user_id), "iat": now, "exp": now + dt.timedelta(minutes=ttl_minutes)}
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


def read_token(token: str, secret: str) -> uuid.UUID | None:
    """The user id in a valid token; None if it is expired, tampered with or not a token."""
    try:
        claims = jwt.decode(
            token, secret, algorithms=[ALGORITHM], options={"require": ["sub", "exp"]}
        )
        return uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None
