from fastapi import FastAPI

from app.api.routes import health


def create_app() -> FastAPI:
    app = FastAPI(
        title="Weather Forecaster",
        description="Current weather and daily forecast for a city.",
        version="0.1.0",
    )
    app.include_router(health.router)
    return app


app = create_app()
