import pytest

from app.core.language import Language
from app.services.weather.weather_codes import WMO_WEATHER_CODES, describe_weather_code


def test_known_codes() -> None:
    assert describe_weather_code(0) == "Clear sky"
    assert describe_weather_code(61) == "Slight rain"
    assert describe_weather_code(99) == "Thunderstorm with heavy hail"


def test_unknown_code() -> None:
    assert describe_weather_code(42) == "Unknown"
    assert describe_weather_code(42, Language.CS) == "Neznámé"


@pytest.mark.parametrize(
    ("language", "expected"),
    [(Language.UK, "Ясне небо"), (Language.CS, "Jasno"), (Language.RU, "Ясное небо")],
)
def test_translations(language: Language, expected: str) -> None:
    assert describe_weather_code(0, language) == expected


@pytest.mark.parametrize("language", [Language.UK, Language.CS, Language.RU])
def test_every_code_is_translated(language: Language) -> None:
    # A copied English text would mean a forgotten translation.
    for code in WMO_WEATHER_CODES:
        assert describe_weather_code(code, language) != describe_weather_code(code), code
