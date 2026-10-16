# Weather Forecaster

Async REST API that shows the current weather and a daily forecast for a city entered by the user.

- Architecture and tech stack: [ARCHITECTURE.md](ARCHITECTURE.md)
- Implementation phases and progress: [ROADMAP.md](ROADMAP.md)

## Requirements

- Python 3.12
- [Poetry](https://python-poetry.org/) 2.x (`brew install poetry` on macOS)

## Setup

```bash
poetry install                    # create the virtualenv and install all dependencies
cp .env.example .env              # local settings (never committed)
poetry run pre-commit install     # run the checks automatically on every git commit
```

## Run the app

```bash
poetry run uvicorn app.main:app --reload
```

`--reload` restarts the server whenever a file changes. Stop it with `Ctrl+C`.

| URL | What you get |
|-----|--------------|
| http://localhost:8000/health | `{"status":"ok"}`: the app is running |
| http://localhost:8000/docs | Swagger UI: interactive API docs, try endpoints from the browser |
| http://localhost:8000/redoc | ReDoc: alternative read-only API docs |

There is no page at `/` yet, so it returns `{"detail":"Not Found"}`. The city search page arrives in Phase 6.

From the terminal:

```bash
curl http://localhost:8000/health
```

## Try the API clients

The REST endpoints come in Phase 2. Until then the clients can be tried from a Python shell:

```bash
poetry run python
```

```python
import asyncio
from app.config import Settings
from app.clients.http import create_http_client
from app.clients.factory import create_geocoding_client
from app.clients.open_meteo_weather import OpenMeteoWeatherClient

async def main(city: str) -> None:
    settings = Settings()
    async with create_http_client(settings) as http:
        location = await create_geocoding_client(settings, http).geocode(city)
        weather = OpenMeteoWeatherClient(http, settings.open_meteo_forecast_url)
        print(location)
        print(await weather.get_current(location.latitude, location.longitude))

asyncio.run(main("Prague"))
```

## Checks

The same checks run in CI on every pull request. Run them before pushing:

```bash
poetry run ruff check .            # lint
poetry run ruff format --check .   # formatting (drop --check to auto-format)
poetry run mypy                    # static type checking (strict)
poetry run pytest                  # tests (add -v to see each test)
poetry run pytest --cov            # tests + coverage report, fails below 80 % (what CI runs)
```

Run a single file, a single test, or tests matching a name:

```bash
poetry run pytest tests/unit/test_weather_codes.py
poetry run pytest tests/unit/test_weather_codes.py::test_known_codes
poetry run pytest -k geocode
```

### Running tests from PyCharm

1. **Settings → Project → Python Interpreter → Add Interpreter → Poetry Environment → Existing**,
   pick the environment Poetry created (`poetry env info --path` prints it).
2. **Settings → Tools → Python Integrated Tools → Testing → Default test runner: `pytest`**.

After that, the green ▶ next to each `test_...` function or at the top of a file runs it with pytest.
Running a test file as a plain Python script does not work: pytest has to collect and run the tests.

Run all pre-commit hooks on the whole repository at once:

```bash
poetry run pre-commit run --all-files
```
