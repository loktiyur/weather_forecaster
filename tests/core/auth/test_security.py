import uuid

import jwt
import pytest

from app.core.auth.security import (
    create_token,
    hash_password,
    read_token,
    verify_password,
)

SECRET = "test-secret-" + "x" * 64  # long enough for every HMAC algorithm
USER_ID = uuid.uuid4()


async def test_a_password_matches_its_hash_only() -> None:
    password_hash = await hash_password("correct horse")

    assert password_hash.startswith("$argon2id$")
    assert await verify_password("correct horse", password_hash) is True
    assert await verify_password("wrong horse", password_hash) is False


async def test_without_a_hash_nothing_matches() -> None:
    # "No such user": the dummy hash is checked, but the answer is always False.
    assert await verify_password("not a real password", None) is False


def test_a_token_carries_the_user_id() -> None:
    assert read_token(create_token(USER_ID, SECRET, ttl_minutes=5), SECRET) == USER_ID


@pytest.mark.parametrize(
    "token",
    [
        create_token(USER_ID, SECRET, ttl_minutes=-1),  # expired
        create_token(USER_ID, "another-secret-with-at-least-32-bytes", ttl_minutes=5),
        jwt.encode({"exp": 9999999999}, SECRET, algorithm="HS256"),  # no user id
        jwt.encode({"sub": "not-a-uuid", "exp": 9999999999}, SECRET, algorithm="HS256"),
        jwt.encode({"sub": str(USER_ID), "exp": 9999999999}, SECRET, algorithm="HS512"),
        "not a token",
    ],
    ids=["expired", "wrong-secret", "no-sub", "bad-sub", "other-algorithm", "garbage"],
)
def test_invalid_tokens_give_no_user(token: str) -> None:
    assert read_token(token, SECRET) is None
