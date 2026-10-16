from app.core.weather_codes import describe_weather_code


def test_known_codes() -> None:
    assert describe_weather_code(0) == "Clear sky"
    assert describe_weather_code(61) == "Slight rain"
    assert describe_weather_code(99) == "Thunderstorm with heavy hail"


def test_unknown_code() -> None:
    assert describe_weather_code(42) == "Unknown"
