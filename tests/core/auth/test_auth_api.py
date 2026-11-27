"""The auth endpoints and dependencies, against the real test Postgres."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.auth.router import COOKIE_NAME
from app.core.auth.security import create_token
from app.core.config import DEV_JWT_SECRET, Settings
from app.core.db import Database
from tests.core.auth.conftest import ANNA, LOGIN, LOGOUT, ME, REGISTER

pytestmark = pytest.mark.postgres


async def test_register_creates_the_account_and_logs_in(client: AsyncClient) -> None:
    response = await client.post(REGISTER, json={**ANNA, "email": "Anna@Example.COM"})

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "anna@example.com"
    assert set(body) == {"id", "email", "created_at", "preferences"}  # never the password hash
    me = await client.get(ME)
    assert me.status_code == 200
    assert me.json() == body


async def test_the_cookie_is_httponly_secure_and_lax(client: AsyncClient) -> None:
    response = await client.post(REGISTER, json=ANNA)

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE_NAME}=")
    for flag in ("HttpOnly", "Secure", "SameSite=lax", "Path=/api", "Max-Age=3600"):
        assert flag in cookie


async def test_cookie_secure_can_be_turned_off(
    app: FastAPI, settings: Settings, client: AsyncClient
) -> None:
    app.state.settings = settings.model_copy(update={"cookie_secure": False})

    response = await client.post(REGISTER, json=ANNA)

    assert "Secure" not in response.headers["set-cookie"]


async def test_an_email_can_register_once(client: AsyncClient) -> None:
    await client.post(REGISTER, json=ANNA)

    response = await client.post(REGISTER, json={**ANNA, "email": "ANNA@example.com"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


async def test_login_after_logout(client: AsyncClient) -> None:
    await client.post(REGISTER, json=ANNA)

    logout = await client.post(LOGOUT)
    assert logout.status_code == 204
    assert (await client.get(ME)).status_code == 401

    login = await client.post(LOGIN, json={**ANNA, "email": " anna@EXAMPLE.com "})
    assert login.status_code == 200
    assert login.json()["email"] == "anna@example.com"
    assert (await client.get(ME)).status_code == 200


@pytest.mark.parametrize(
    "credentials",
    [{**ANNA, "password": "wrong horse"}, {**ANNA, "email": "nobody@example.com"}],
    ids=["wrong-password", "unknown-email"],
)
async def test_failed_logins_look_the_same(
    client: AsyncClient, credentials: dict[str, str]
) -> None:
    await client.post(REGISTER, json=ANNA)
    await client.post(LOGOUT)

    response = await client.post(LOGIN, json=credentials)

    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "UNAUTHORIZED", "message": "Wrong email or password."}
    }
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize(
    "cookie",
    [
        None,
        "not-a-token",
        create_token(uuid.uuid4(), DEV_JWT_SECRET, ttl_minutes=5),
    ],
    ids=["no-cookie", "garbage", "deleted-user"],
)
async def test_me_without_a_valid_login_is_401(client: AsyncClient, cookie: str | None) -> None:
    headers = {"Cookie": f"{COOKIE_NAME}={cookie}"} if cookie else {}

    response = await client.get(ME, headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_an_expired_login_is_401(client: AsyncClient, settings: Settings) -> None:
    user_id = (await client.post(REGISTER, json=ANNA)).json()["id"]
    client.cookies.clear()
    expired = create_token(uuid.UUID(user_id), settings.jwt_secret, ttl_minutes=-1)

    response = await client.get(ME, headers={"Cookie": f"{COOKIE_NAME}={expired}"})

    assert response.status_code == 401


async def test_a_password_is_kept_exactly_as_typed(client: AsyncClient) -> None:
    password = "  correct horse  "
    await client.post(REGISTER, json={**ANNA, "password": password})
    await client.post(LOGOUT)

    trimmed = await client.post(LOGIN, json={**ANNA, "password": password.strip()})
    as_typed = await client.post(LOGIN, json={**ANNA, "password": password})

    assert trimmed.status_code == 401
    assert as_typed.status_code == 200


@pytest.mark.parametrize(
    ("path", "body", "field"),
    [
        (REGISTER, {**ANNA, "email": "not-an-email"}, "email"),
        (REGISTER, {**ANNA, "password": "short"}, "password"),
        (REGISTER, {**ANNA, "password": "x" * 129}, "password"),
        (REGISTER, {**ANNA, "password": " " * 8}, "password"),
        (REGISTER, {**ANNA, "password": "\t   abc   \n"}, "password"),
        (REGISTER, {"email": ANNA["email"]}, "password"),
        (LOGIN, {**ANNA, "password": ""}, "password"),
    ],
)
async def test_invalid_bodies_are_422(
    client: AsyncClient, path: str, body: dict[str, str], field: str
) -> None:
    response = await client.post(path, json=body)

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == field


async def test_the_database_keeps_emails_lowercase(clean_database: Database) -> None:
    with pytest.raises(IntegrityError):
        async with clean_database.engine.begin() as connection:
            await connection.execute(
                text("INSERT INTO auth.users (email, password_hash) VALUES ('Anna@x.cz', 'h')")
            )
