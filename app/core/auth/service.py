"""Registering and logging in: the users table and the password checks."""

from fastapi import HTTPException, status
from sqlalchemy import select
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
