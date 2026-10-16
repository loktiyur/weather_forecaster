# Roadmap

Implementation phases for the Weather Forecaster. Architecture and stack: [ARCHITECTURE.md](ARCHITECTURE.md).

**Workflow:** each phase is developed on its own branch (`phase-N-short-name`) and merged into `main` through a pull request. `main` is protected: a PR can only be merged when the CI pipeline is green. Each phase also extends the pipeline when it adds something new to check.

Status legend: `[ ]` to do · `[x]` done

---

## Phase 0 — Project setup + CI pipeline
Branch: `phase-0-setup-ci`

- [x] Poetry project (`pyproject.toml`) with `main` and `dev` dependency groups, Python 3.12
- [x] `app/` package skeleton (other packages from ARCHITECTURE.md §7 are added by the phase that needs them)
- [x] `.gitignore`, `.env.example`, short `README.md`
- [x] ruff (lint + format) and mypy (strict) config in `pyproject.toml`
- [x] pre-commit hooks (ruff, ruff-format, mypy, end-of-file/trailing-whitespace)
- [x] Minimal FastAPI app with `GET /health` + one smoke test (pytest fails with "no tests collected" otherwise)
- [x] `.github/workflows/ci.yml`: install Poetry with cache → `ruff check` → `ruff format --check` → `mypy` → `pytest`
- [ ] Branch protection on `main`: require the CI check to pass, require PR *(manual, in GitHub repo settings)*

**CI after this phase:** lint · format · type-check · tests

---

## Phase 1 — External API clients (refactor of `modules/connector.py`)
Branch: `phase-1-clients`

- [ ] `config.py` with `pydantic-settings` (replace module-level `os.environ[...]`)
- [ ] Domain exceptions: `CityNotFoundError`, `UpstreamServiceError`, `UpstreamTimeoutError`
- [ ] Pydantic models: `Location`, `CurrentWeather`, `DailyForecast`
- [ ] `GeocodingClient` protocol + Open-Meteo geocoding implementation
- [ ] (optional) GeoNames implementation from the existing `geopy` code
- [ ] Open-Meteo weather client: `current=` and `daily=` params, returns models (no pandas)
- [ ] WMO weather code → description mapping
- [ ] Unit tests with `respx` + JSON fixtures: success, not found, 5xx, timeout
- [ ] Evolve `modules/connector.py` into `app/clients/` (use `git mv` to keep its history; the prototype's flow, params and `to_thread` handling carry over)

**CI additions:** `pytest-cov` with coverage report; fail under 80 %

---

## Phase 2 — REST API layer
Branch: `phase-2-api`

- [ ] `create_app()` + lifespan managing a shared `httpx.AsyncClient`
- [ ] `WeatherService` (geocode → fetch), injected via `Depends`
- [ ] `GET /api/v1/weather/current`, `GET /api/v1/weather/forecast`, `GET /api/v1/locations/search`
- [ ] Query validation (`city` length, `days` 1–16, `units` enum)
- [ ] Exception handlers → unified error JSON (404 / 422 / 502 / 504)
- [ ] API tests via `httpx.AsyncClient` + `ASGITransport` and `dependency_overrides`
- [ ] Check Swagger at `/docs` looks clean (descriptions, examples)

**CI additions:** none required (coverage gate now covers the API)

---

## Phase 3 — Redis cache
Branch: `phase-3-redis`

- [ ] `docker-compose.yml` for local infrastructure (the app itself runs locally with `uvicorn --reload`): `redis` service
- [ ] `redis.asyncio` client in lifespan, `REDIS_URL` setting
- [ ] `CacheService` with keys/TTLs from ARCHITECTURE.md §6
- [ ] `cached: true/false` in responses
- [ ] Graceful degradation when Redis is unavailable
- [ ] Unit tests with `fakeredis`: hit, miss, Redis down

**CI additions:** none (fakeredis, no service container needed)

---

## Phase 4 — PostgreSQL search history
Branch: `phase-4-postgres`

- [ ] Add `db` (dev, persistent volume) and `db-test` (tmpfs, separate port) Postgres services to `docker-compose.yml`
- [ ] SQLAlchemy 2.0 async engine/session, `asyncpg`
- [ ] `SearchHistory` model + indexes
- [ ] Alembic setup + first migration
- [ ] `SearchHistoryRepository` (insert, recent, popular)
- [ ] Save searches via `BackgroundTasks`
- [ ] `GET /api/v1/history`, `GET /api/v1/history/popular`
- [ ] `GET /health/ready` checks Redis + Postgres
- [ ] Repository + endpoint tests against a real Postgres

**CI additions:** `postgres:16` service container · `alembic upgrade head` before tests · `alembic check` (models and migrations in sync)

---

## Phase 5 — App container image
Branch: `phase-5-docker`

The app runs locally during development; the image is what gets deployed and what CI smoke-tests.

- [ ] Multi-stage `Dockerfile` (Poetry export → slim runtime image, non-root user)
- [ ] `api` service in `docker-compose.yml` under a `full` profile (`docker compose --profile full up`), migration on start
- [ ] Healthchecks for all compose services
- [ ] `.dockerignore`
- [ ] README: dev mode (`docker compose up` + `uvicorn --reload`) vs full stack

**CI additions:** build the Docker image · smoke test: start compose, `curl /health/ready`

---

## Phase 6 — Minimal UI
Branch: `phase-6-ui`

- [ ] Jinja2 template `index.html`: city input → current weather + forecast
- [ ] Show resolved location (handles ambiguous names) and error messages
- [ ] Route test for the page

**CI additions:** none

---

## Phase 7 — Polish
Branch: `phase-7-polish`

- [ ] Retries with `tenacity` for transient upstream errors
- [ ] Structured logging with request id middleware
- [ ] README: screenshots, example `curl` calls, architecture link
- [ ] Tag `v1.0.0`

**CI additions:** on tag `v*`, push image to GitHub Container Registry (CD step)

---

## Phase 8 — Optional extensions
- [ ] Deploy to GCP Cloud Run with Terraform (CI: `terraform fmt -check` + `terraform validate`)
- [ ] Rate limiting
- [ ] Vue.js + TypeScript frontend with autocomplete
- [ ] Weather alerts worker with RabbitMQ
- [ ] gRPC interface alongside REST
- [ ] Prometheus metrics
