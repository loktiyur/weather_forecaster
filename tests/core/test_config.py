import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def make_settings(**overrides: object) -> Settings:
    # _env_file=None: tests must not depend on the developer's local .env
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_geonames_without_username_is_rejected() -> None:
    with pytest.raises(ValidationError, match="GEONAMES_USERNAME is required"):
        make_settings(geocoding_provider="geonames")


def test_settings_are_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_TIMEOUT_SECONDS", "2.5")

    assert make_settings().http_timeout_seconds == 2.5


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
