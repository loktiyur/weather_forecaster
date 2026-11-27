"""Registering and logging in: the users table and the password checks."""

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import Text, literal, select, update
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import UserRow
from app.core.auth.security import hash_password, verify_password


async def register(session: AsyncSession, email: str, password: str) -> UserRow:
    user = UserRow(email=email, password_hash=await hash_password(password))
    try:
        async with session.begin():
            session.add(user)
    except IntegrityError as exc:
        # The UNIQUE constraint decides, not a lookup first: two parallel registrations with
        # the same email cannot both get through.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An account with this email already exists."
        ) from exc
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> UserRow:
    user = await session.scalar(select(UserRow).where(UserRow.email == email))
    if not await verify_password(password, user.password_hash if user else None):
        # One message for both cases, so the answer does not reveal who has an account.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password.")
    assert user is not None  # verify_password is False without a user
    return user


async def update_preferences(
    session: AsyncSession, user_id: uuid.UUID, changes: dict[str, Any]
) -> dict[str, Any]:
    """Applies `changes` (a value: set it, None: remove it) and returns the stored preferences.

    One UPDATE, `(preferences || set) - removed`, so two parallel changes of different
    fields both survive (no read-modify-write in Python).
    """
    chosen = {key: value for key, value in changes.items() if value is not None}
    removed = [key for key, value in changes.items() if value is None]
    # self_group(): parentheses around the `||`. Postgres binds `-` tighter, and without them
    # `a || b - c` would remove the keys from `b` only, never from the stored value.
    new_value = (
        UserRow.preferences.op("||")(literal(chosen, JSONB))
        .self_group()
        .op("-")(literal(removed, ARRAY(Text)))
    )
    async with session.begin():
        stored = await session.scalar(
            update(UserRow)
            .where(UserRow.id == user_id)
            .values(preferences=new_value)
            .returning(UserRow.preferences)
        )
    return stored or {}
