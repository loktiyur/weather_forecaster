class WeatherForecasterError(Exception):
    """Base class for all domain errors of the application."""


class CityNotFoundError(WeatherForecasterError):
    def __init__(self, city: str) -> None:
        self.city = city
        super().__init__(f"No place found for '{city}'.")


class NotACityError(WeatherForecasterError):
    """The name is a country ("Germany"): there is no single place to show the weather for."""

    def __init__(self, name: str, country: str) -> None:
        self.name = name
        self.country = country
        super().__init__(f"'{country}' is a country, not a city.")


class LocationNotFoundError(WeatherForecasterError):
    """No populated place has this id."""

    def __init__(self, location_id: int) -> None:
        self.location_id = location_id
        super().__init__(f"No place found with id {location_id}.")


class NotSupportedError(WeatherForecasterError):
    """The configured provider cannot do this (e.g. GeoNames via geopy: lookup by id)."""

    def __init__(self, service: str, feature: str) -> None:
        self.service = service
        self.feature = feature
        super().__init__(f"{service} does not support {feature}.")


class UpstreamServiceError(WeatherForecasterError):
    """An external API returned an error or a response we could not understand."""

    def __init__(self, service: str, detail: str) -> None:
        self.service = service
        self.detail = detail
        super().__init__(f"{service} error: {detail}")


class UpstreamTimeoutError(WeatherForecasterError):
    def __init__(self, service: str) -> None:
        self.service = service
        super().__init__(f"{service} did not respond in time.")
