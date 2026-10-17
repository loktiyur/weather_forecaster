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
| http://localhost:8000/docs | Swagger UI: interactive API docs, try every endpoint from the browser |
| http://localhost:8000/redoc | ReDoc: alternative read-only API docs |
| http://localhost:8000/health | `{"status":"ok"}`: the app is running |

There is no page at `/` yet (it returns a `NOT_FOUND` error). The city search page arrives in Phase 6.

## API

| Endpoint | Query parameters |
|----------|------------------|
| `GET /api/v1/weather/current` | `city` (required), `country` (ISO code, e.g. `CZ`), `units` (`metric` / `imperial`) |
| `GET /api/v1/weather/forecast` | same as above + `days` (1-16, default 7) |
| `GET /api/v1/locations/search` | `q` (required), `country`, `limit` (1-10, default 5) |
| `GET /health` | |

```bash
curl "http://localhost:8000/api/v1/weather/current?city=Prague"
curl "http://localhost:8000/api/v1/weather/current?city=Paris&country=US&units=imperial"
curl "http://localhost:8000/api/v1/weather/forecast?city=Kyiv&days=3"
curl "http://localhost:8000/api/v1/locations/search?q=Springfield&limit=3"
```

Every error uses the same format:

```bash
curl "http://localhost:8000/api/v1/weather/current?city=Qwertyuiopxyz"
# 404 {"error":{"code":"CITY_NOT_FOUND","message":"No place found for 'Qwertyuiopxyz'."}}

curl "http://localhost:8000/api/v1/weather/forecast?city=Prague&days=40"
# 422 {"error":{"code":"VALIDATION_ERROR","message":"Invalid request parameters.",
#      "details":[{"field":"days","location":"query","message":"Input should be less than or equal to 16"}]}}
```

| Status | `code` | When |
|--------|--------|------|
| 404 | `CITY_NOT_FOUND` | No place matches the name |
| 404 / 405 | `NOT_FOUND` / `METHOD_NOT_ALLOWED` | Unknown URL / wrong HTTP method |
| 422 | `VALIDATION_ERROR` | Invalid query parameters (`details` lists each one) |
| 502 | `UPSTREAM_ERROR` | Open-Meteo / GeoNames returned an error |
| 504 | `UPSTREAM_TIMEOUT` | Open-Meteo / GeoNames did not answer in time |

## Checks

Tasks are defined in `pyproject.toml` under `[tool.poe.tasks]` and run with [poethepoet](https://poethepoet.natn.io/).
CI runs exactly the same tasks.

```bash
poetry run poe format-code     # fix lint issues + format everything (run this when the format check fails)
poetry run poe check           # everything CI runs: lint, format check, type check, tests with coverage
```

Individual tasks:

```bash
poetry run poe lint            # ruff check
poetry run poe format-check    # ruff format --check (changes nothing)
poetry run poe typecheck       # mypy, strict
poetry run poe test            # pytest; extra args pass through: poe test -k geocode -v
poetry run poe test-cov        # pytest with coverage, fails below 80 %
poetry run poe --help          # list all tasks
```

Tip: after `eval $(poetry env activate)` the `poetry run` prefix can be dropped (`poe check`).

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
