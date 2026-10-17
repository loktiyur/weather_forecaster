from typing import Annotated, cast

from fastapi import Depends, Request

from app.services.weather_service import WeatherService


def get_weather_service(request: Request) -> WeatherService:
    """The service is built once in the app lifespan; tests replace it via dependency_overrides."""
    return cast(WeatherService, request.app.state.weather_service)


WeatherServiceDep = Annotated[WeatherService, Depends(get_weather_service)]
