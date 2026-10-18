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

- [x] `config.py` with `pydantic-settings` (replace module-level `os.environ[...]`)
- [x] Domain exceptions: `CityNotFoundError`, `UpstreamServiceError`, `UpstreamTimeoutError`
- [x] Pydantic models: `Location`, `CurrentWeather`, `DailyForecastDay`
- [x] `GeocodingClient` abstract base class + Open-Meteo geocoding implementation
- [x] GeoNames implementation from the existing `geopy` code (selected with `GEOCODING_PROVIDER=geonames`)
- [x] Open-Meteo weather client: `current=` and `daily=` params, returns models (no pandas)
- [x] WMO weather code → description mapping
- [x] Unit tests with `respx` + JSON fixtures: success, not found, 5xx, timeout
- [x] Evolve `modules/connector.py` into `app/clients/` (use `git mv` to keep its history; the prototype's flow, params and `to_thread` handling carry over)

**CI additions:** `pytest-cov` with coverage report; fail under 80 % (`pytest --cov` in CI; plain `pytest` skips coverage so single files can be run)

---

## Phase 2 — REST API layer
Branch: `phase-2-api`

- [x] `create_app()` + lifespan managing a shared `httpx.AsyncClient`
- [x] `WeatherService` (geocode → fetch), injected via `Depends`; depends on `GeocodingClient` / `WeatherClient` interfaces
- [x] `GET /api/v1/weather/current`, `GET /api/v1/weather/forecast`, `GET /api/v1/locations/search`
- [x] Query validation with Pydantic query models (`city` length + whitespace trimming, `country` ISO code, `days` 1–16, `units` enum)
- [x] Exception handlers → unified error JSON (404 / 405 / 422 / 502 / 504), upstream details logged, not leaked
- [x] API tests via `httpx.AsyncClient` + `ASGITransport` and `dependency_overrides`
- [x] Check Swagger at `/docs` looks clean (descriptions, examples, documented error responses)
- [ ] `Cache-Control` response headers *(moved to Phase 3, together with the Redis TTLs)*

**CI additions:** none required (coverage gate now covers the API)

---

## Phase 3 — Redis cache
Branch: `phase-3-redis`

Redis runs in Docker. Tests use a **real** Redis, not fakeredis: locally the `redis-test` container, in CI a GitHub Actions service container.

**Infrastructure**
- [x] `docker-compose.yml`: `redis` (dev, port 6379, persistent volume) and `redis-test` (port 6380, no persistence), both `redis:7.4-alpine` with healthchecks. The app itself keeps running on the host with `uvicorn --reload`
- [x] `REDIS_URL` setting; `redis.asyncio` client created in the lifespan and closed on shutdown

**Caching**
- [x] `Cache` interface (Protocol) + `RedisCache` implementation (string values, TTL per key; the service serialises models to JSON with Pydantic), key layout in `app/cache/keys.py`
- [x] Cache-aside in `WeatherService` with the keys/TTLs from ARCHITECTURE.md §6: geocoding 7 days, current weather 10 min, forecast 1 h
- [x] `cached: true/false` in weather responses
- [x] Graceful degradation: if Redis is down, log a warning and call the upstream API as if there were no cache
- [x] `Cache-Control: public, max-age=<TTL>` response headers matching the TTLs (REST "cacheable" constraint)
- [x] `GET /health/ready` checks Redis (`503` if unreachable); the Postgres check is added in Phase 4

**Tests**
- [x] `integration` pytest marker for tests that need real infrastructure
- [x] `RedisCache` integration tests against real Redis: get/set, JSON round-trip, TTL expiry, Redis down (client pointed at a closed port)
- [x] `WeatherService` unit tests with a small in-memory `Cache` test double (a double of *our own* interface, not an imitation of Redis): hit skips the HTTP call, miss stores the result, cache errors are ignored
- [x] Integration tests fail with a hint (`docker compose up -d redis-test`) when the test Redis is not reachable, locally and in CI; they are never skipped
- [x] poe tasks: `test-unit` (`-m "not integration"`), `test-integration` (`-m integration`); `test-cov` runs everything with the coverage gate

**CI additions:** the pipeline is split into two jobs, and both are required checks in the `main` ruleset:
- `checks` (check name `Lint, type-check, test`, unchanged so the existing ruleset keeps working): lint · format check · type check · unit + API tests (no Docker)
- `Redis integration`: `redis:7.4-alpine` service container · integration tests · coverage gate over the whole suite

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
- [ ] `GET /health/ready` also checks Postgres
- [ ] Repository + endpoint tests against the real `db-test` Postgres (`integration` marker)

**CI additions:** `postgres:16` service container in the `integration` job · `alembic upgrade head` before tests · `alembic check` (models and migrations in sync)

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
