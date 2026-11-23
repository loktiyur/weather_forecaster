"""/auth/register, /auth/login, /auth/logout, /me, and the dependencies that tell who is calling.

The login token is a JWT in an httpOnly cookie: page scripts cannot read it, and the browser
sends it to the API (same origin) by itself.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import APIKeyCookie
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.core.auth import service
from app.core.auth.models import UserRow
from app.core.auth.schemas import LoginRequest, RegisterRequest, UserResponse
from app.core.auth.security import create_token, read_token
from app.core.config import Settings
from app.core.db import get_session

COOKIE_NAME = "access_token"
COOKIE_PATH = "/api"  # the API only: the cookie is not sent with page and asset requests

# Documents the cookie in OpenAPI; auto_error=False: a missing cookie is handled below.
_cookie = APIKeyCookie(name=COOKIE_NAME, auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


async def optional_user(
    token: Annotated[str | None, Depends(_cookie)], session: SessionDep, settings: SettingsDep
) -> UserRow | None:
    """The logged-in user, or None for guests (and for expired or invalid tokens)."""
    user_id = read_token(token, settings.jwt_secret) if token else None
    # A token can outlive its user: a deleted account counts as not logged in.
    return await session.get(UserRow, user_id) if user_id else None


async def current_user(user: Annotated[UserRow | None, Depends(optional_user)]) -> UserRow:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Log in to use this endpoint.")
    return user


OptionalUser = Annotated[UserRow | None, Depends(optional_user)]
CurrentUser = Annotated[UserRow, Depends(current_user)]

DESCRIPTIONS = {
    401: "Not logged in, or the login expired (`UNAUTHORIZED`); for login: wrong email or password",
    409: "An account with this email already exists (`CONFLICT`)",
    422: "Invalid request body",
}


def error_docs(*statuses: int) -> dict[int | str, dict[str, Any]]:
    return errors.error_docs(*statuses, descriptions=DESCRIPTIONS)


def _log_in(response: Response, user: UserRow, settings: Settings) -> UserResponse:
    response.set_cookie(
        COOKIE_NAME,
        create_token(user.id, settings.jwt_secret, settings.jwt_ttl_minutes),
        max_age=settings.jwt_ttl_minutes * 60,
        path=COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return UserResponse.model_validate(user)


router = APIRouter(tags=["auth"])


@router.post(
    "/auth/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    summary="Create an account and log in",
    responses=error_docs(409, 422),
)
async def register(
    body: RegisterRequest, session: SessionDep, settings: SettingsDep, response: Response
) -> UserResponse:
    """The email is stored lower-cased; the password needs 8 to 128 characters."""
    user = await service.register(session, body.email, body.password)
    return _log_in(response, user, settings)


@router.post(
    "/auth/login",
    response_model=UserResponse,
    summary="Log in",
    responses=error_docs(401, 422),
)
async def login(
    body: LoginRequest, session: SessionDep, settings: SettingsDep, response: Response
) -> UserResponse:
    """Sets the login cookie, valid for `JWT_TTL_MINUTES`."""
    user = await service.authenticate(session, body.email, body.password)
    return _log_in(response, user, settings)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Log out")
async def logout(response: Response, settings: SettingsDep) -> None:
    """Deletes the login cookie. Works without being logged in, so it can always be called."""
    response.delete_cookie(
        COOKIE_NAME, path=COOKIE_PATH, secure=settings.cookie_secure, httponly=True, samesite="lax"
    )


@router.get(
    "/me", response_model=UserResponse, summary="The logged-in user", responses=error_docs(401)
)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
