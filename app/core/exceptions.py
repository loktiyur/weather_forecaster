class WeatherForecasterError(Exception):
    """Base class for all domain errors of the application."""


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
