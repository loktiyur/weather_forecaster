# Weather Forecaster

Async REST API that shows the current weather and a daily forecast for a city entered by the user.

- Architecture and tech stack: [ARCHITECTURE.md](ARCHITECTURE.md)
- Implementation phases and progress: [ROADMAP.md](ROADMAP.md)

## Requirements

- Python 3.12
- [Poetry](https://python-poetry.org/) 2.x (`brew install poetry` on macOS)
- Docker with Docker Compose (for Redis)

## Setup

```bash
poetry install                    # create the virtualenv and install all dependencies
cp .env.example .env              # local settings (never committed)
poetry run pre-commit install     # run the checks automatically on every git commit
```

## Infrastructure (Docker)

Docker Compose runs only the infrastructure; the app runs on your machine.

```bash
docker compose up -d       # start Redis (dev, port 6379) and redis-test (port 6380)
docker compose ps          # both should be "healthy"
docker compose down        # stop them (the dev cache survives in a volume)
```

| Service | Port | Used by |
|---------|------|---------|
| `redis` | 6379 | the app (`REDIS_URL`), keeps its data across restarts |
| `redis-test` | 6380 | integration tests only, emptied by every test, nothing saved to disk |

Without Redis the app still works: every request calls the weather APIs, a warning is logged and `/health/ready` returns `503`.

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
| http://localhost:8000/health/ready | `200` if Redis is reachable, `503` if not |

There is no page at `/` yet (it returns a `NOT_FOUND` error). The web frontend arrives in Phase 5 (see ROADMAP.md).

## API

| Endpoint | Query parameters |
|----------|------------------|
| `GET /api/v1/weather/current` | `city` (required), `country` (ISO code, e.g. `CZ`), `units` (`metric` / `imperial`) |
| `GET /api/v1/weather/forecast` | same as above + `days` (1-16, default 7) |
| `GET /api/v1/locations/search` | `q` (required), `country`, `limit` (1-10, default 5) |
| `GET /health`, `GET /health/ready` | |

```bash
curl "http://localhost:8000/api/v1/weather/current?city=Prague"
curl "http://localhost:8000/api/v1/weather/current?city=Paris&country=US&units=imperial"
curl "http://localhost:8000/api/v1/weather/forecast?city=Kyiv&days=3"
curl "http://localhost:8000/api/v1/locations/search?q=Springfield&limit=3"
```

### Caching

Results are cached in Redis: places for 7 days, current weather for 10 minutes, forecasts for 1 hour.
`"cached": true` in the response means the weather came from the cache, and the `Cache-Control` header
lets browsers reuse the response too:

```bash
curl -i "http://localhost:8000/api/v1/weather/current?city=Prague"
# HTTP/1.1 200 OK
# cache-control: public, max-age=600
# ... "cached":false}            ← first call: fetched from Open-Meteo
# (call again)       "cached":true}   ← served from Redis
```

Look into the cache:

```bash
docker compose exec redis redis-cli --scan          # list keys (copy exact names from here)
docker compose exec redis redis-cli ttl geo:prague: # seconds left (note the trailing colon)
docker compose exec redis redis-cli monitor         # watch every command live, Ctrl+C to stop
docker compose exec redis redis-cli flushdb         # empty the dev cache
```

`ttl` returns the seconds left, `-2` if the key does not exist (wrong name, or already expired:
current weather lives only 10 minutes) and `-1` if it has no expiry (never the case here).
Place keys end with the country code, empty when none was given: `geo:prague:` vs `geo:prague:CZ`.

### Errors

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
poetry run poe check           # lint, format check, type check, all tests with coverage (needs redis-test, see below)
```

Individual tasks:

```bash
poetry run poe lint              # ruff check
poetry run poe format-check      # ruff format --check (changes nothing)
poetry run poe typecheck         # mypy, strict
poetry run poe test-unit         # unit + API tests, no Docker needed
poetry run poe test-integration  # tests against the real redis-test container
poetry run poe test              # all tests; extra args pass through: poe test -k geocode -v
poetry run poe test-cov          # all tests with coverage, fails below 80 %
poetry run poe --help            # list all tasks
```

### Unit vs. integration tests

- **Unit + API tests** never need infrastructure: external APIs are mocked with respx and the cache
  is a small in-memory test double of our own `Cache` interface.
- **Integration tests** (`@pytest.mark.integration`, in `tests/integration/`) run against a real Redis
  in Docker. **The `redis-test` container must be running, otherwise these tests fail**
  (with a message telling you how to start it):
  ```bash
  docker compose up -d redis-test     # Docker Desktop / Rancher Desktop must be running
  docker compose ps                   # redis-test should be "healthy"
  poetry run poe test-integration
  ```
  `poe test`, `poe test-cov` and `poe check` run all tests, so they need `redis-test` running too.
  Without Docker, use `poe test-unit`.

### CI

Two jobs run on every pull request; both are required checks for merging into `main`:

| Job | Steps |
|-----|-------|
| `Lint, type-check, test` | lint, format check, mypy, unit + API tests |
| `Redis integration` | starts `redis:7.4-alpine` as a service container, runs the integration tests, then all tests with the coverage gate |

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
