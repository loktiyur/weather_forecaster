# Roadmap

Implementation phases for the Weather Forecaster. Architecture and stack: [ARCHITECTURE.md](ARCHITECTURE.md).

The project ships in two releases:

- **Release 1.0: basic weather app.** The weather backend (done in Phases 0–3), packaged in Docker, plus a web frontend. No database: nothing in the basic app needs permanent storage.
- **Release 2.0: weather, trips and statistics.** The backend is restructured into `core` + three services (weather, trips, stats), PostgreSQL is added, and users can log in, plan trips, save places and see their statistics. Each phase includes its frontend page, so every feature is usable when it is merged.

**Workflow:** each phase is developed on its own branch (`phase-N-short-name`) and merged into `main` through a pull request. `main` is protected by a ruleset: a PR can only be merged when all required CI checks are green. Each phase also extends the pipeline when it adds something new to check.

Status legend: `[ ]` to do · `[x]` done

---

# Release 1.0: basic weather app

## Phase 0 — Project setup + CI pipeline
Branch: `phase-0-setup-ci`

- [x] Poetry project (`pyproject.toml`) with `main` and `dev` dependency groups, Python 3.12
- [x] `app/` package skeleton (other packages are added by the phase that needs them)
- [x] `.gitignore`, `.env.example`, short `README.md`
- [x] ruff (lint + format) and mypy (strict) config in `pyproject.toml`
- [x] pre-commit hooks (ruff, ruff-format, mypy, end-of-file/trailing-whitespace)
- [x] Minimal FastAPI app with `GET /health` + one smoke test (pytest fails with "no tests collected" otherwise)
- [x] `.github/workflows/ci.yml`: install Poetry with cache → `ruff check` → `ruff format --check` → `mypy` → `pytest`
- [x] Ruleset on `main`: require a PR and the CI checks to pass *(manual, in GitHub repo settings)*

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
- [x] `Cache-Control` response headers *(moved to Phase 3, together with the Redis TTLs)*

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
- [x] Cache-aside in `WeatherService` with the keys/TTLs from ARCHITECTURE.md §8: geocoding 7 days, current weather 10 min, forecast 1 h
- [x] `cached: true/false` in weather responses
- [x] Graceful degradation: if Redis is down, log a warning and call the upstream API as if there were no cache
- [x] `Cache-Control: public, max-age=<TTL>` response headers matching the TTLs (REST "cacheable" constraint)
- [x] `GET /health/ready` checks Redis (`503` if unreachable)

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

## Phase 4 — Container images + full stack
Branch: `phase-4-docker`

Development keeps running the app on the host (`uvicorn --reload`). The image is what gets deployed and what CI checks.

- [ ] Multi-stage `Dockerfile` for the API: Poetry installs into a virtualenv in a build stage → slim Python runtime stage, non-root user, `HEALTHCHECK` on `/health`
- [ ] `.dockerignore` (tests, caches, `.git`, `.env`, `frontend/node_modules`)
- [ ] `api` service in `docker-compose.yml` under the `full` profile, with `REDIS_URL=redis://redis:6379/0` and `depends_on: redis (healthy)`
- [ ] `docker compose --profile full up` starts the whole basic app (api + redis); `docker compose up` still starts only the infrastructure
- [ ] Image runs Uvicorn without `--reload`, settings only from environment variables
- [ ] README: development mode vs full stack

**CI additions:** new job `Docker image`: build the image · start the `full` profile · smoke test `curl /health/ready` and one weather request · shut down. Required check in the ruleset.

---

## Phase 5 — Frontend (basic UI)
Branch: `phase-5-frontend`

A Vue 3 + TypeScript single-page app in `frontend/`, using only the public REST API (ARCHITECTURE.md §9).

**Setup**
- [ ] `frontend/` with Vite, Vue 3, TypeScript (strict), Vue Router, ESLint + Prettier, Vitest + Vue Test Utils
- [ ] API types generated from the backend's `/openapi.json` with `openapi-typescript`; typed calls with `openapi-fetch`
- [ ] Dev server proxies `/api` to `localhost:8000` (no CORS setup needed)

**Pages and components**
- [ ] Search page: city input → current weather card + daily forecast list
- [ ] Ambiguous names: place picker using `/locations/search` (shows region + country), optional country filter
- [ ] Units toggle (metric / imperial), remembered in `localStorage`
- [ ] Loading, empty and error states mapped from the API error codes (`CITY_NOT_FOUND`, `UPSTREAM_TIMEOUT`, …)
- [ ] Responsive layout (phone width up to desktop)

**Packaging**
- [ ] Multi-stage `frontend/Dockerfile`: Node builds the static files → nginx serves them and proxies `/api` to the `api` service
- [ ] `web` service in the `full` profile: `docker compose --profile full up` → open http://localhost:8080

**Tests**
- [ ] Vitest component tests with a mocked API client (search, place picker, error states)

**CI additions:** new job `Frontend`: `npm ci` · lint · type check (`vue-tsc`) · unit tests · build · **generated API types are up to date** (regenerate from the backend's OpenAPI schema and fail on a diff). The `Docker image` job also builds the `web` image and smoke-tests http://localhost:8080. Required check in the ruleset.

---

## Phase 6 — Release 1.0
Branch: `phase-6-release`

- [ ] Retries with `tenacity` for transient upstream errors (timeouts, 5xx), with backoff and a small attempt limit
- [ ] Structured logging (JSON in containers, readable locally) with a request id middleware (`X-Request-ID` in responses and logs)
- [ ] `LOG_LEVEL` setting
- [ ] README: screenshots, quick start (`docker compose --profile full up`), API examples, links to the docs
- [ ] `CHANGELOG.md`
- [ ] Tag `v1.0.0`

**CI additions:** on tag `v*`: build and push the `api` and `web` images to GitHub Container Registry (first CD step).

---

# Release 2.0: weather, trips and statistics

## Phase 7 — Restructure into core + services
Branch: `phase-7-restructure`

The code moves into the structure from ARCHITECTURE.md §6. **No behaviour change**: the existing tests prove the move is safe, and the API contract (OpenAPI schema) stays identical.

- [ ] `app/core/`: config, HTTP client + `get_json`, cache (`Cache`, `RedisCache`), errors, shared exceptions
- [ ] `app/services/weather/`: router, service, schemas, cache keys, `providers/` (renamed from `clients/`: Open-Meteo, GeoNames)
- [ ] Tests mirror the new layout
- [ ] Dependency rules written down as import-linter contracts in `pyproject.toml` (services → core only; no imports from core into services)

**CI additions:** new step `Architecture` (`lint-imports`) in the `Lint, type-check, test` job. The `Frontend` job's "API types up to date" check proves the contract did not change.

---

## Phase 8 — PostgreSQL foundation
Branch: `phase-8-postgres`

- [ ] `db` (dev, port 5432, persistent volume) and `db-test` (port 5433, tmpfs) as `postgres:16-alpine` in `docker-compose.yml`; `api` in the `full` profile depends on `db`
- [ ] `app/core/db.py`: SQLAlchemy 2.0 async engine + session dependency (`asyncpg`)
- [ ] Alembic with async support; one schema per service (ARCHITECTURE.md §8); first migration creates schema `weather`
- [ ] `weather.locations`: places stored once with a stable id, upserted from geocoding results (`INSERT … ON CONFLICT`)
- [ ] `id` added to `Location` in API responses; `GET /api/v1/locations/{id}`
- [ ] `GET /health/ready` also checks Postgres
- [ ] Migrations run on container start in the `full` profile
- [ ] Integration tests against `db-test` (fail when it is not running, like Redis); markers `redis` and `postgres` under `integration`

**CI additions:**
- new job `Postgres integration`: `postgres:16-alpine` service container · `alembic upgrade head` · `alembic check` (models and migrations in sync) · Postgres integration tests
- coverage is combined: each test job uploads its coverage data, a `Coverage` job merges it and applies the 80 % gate

---

## Phase 9 — Authentication
Branch: `phase-9-auth`

- [ ] `app/core/auth/`: schema `auth`, table `users` (email unique, password hash, `preferences JSONB`, timestamps)
- [ ] Password hashing with Argon2 (`pwdlib`)
- [ ] `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/me`
- [ ] JWT (`PyJWT`) in an **httpOnly, Secure, SameSite=Lax cookie**, not readable by page scripts
- [ ] `current_user` / `optional_user` dependencies for the services
- [ ] `PATCH /api/v1/me/preferences`: validated by a Pydantic model (units, language, home place); weather endpoints use the user's units when `units` is not given
- [ ] Frontend: register / login / logout, user menu, preferences page

**CI additions:** auth tests (hashing, token expiry, cookie flags, protected routes return `401`)

---

## Phase 10 — Statistics service
Branch: `phase-10-stats`

- [ ] `app/core/events.py`: small in-process publish/subscribe
- [ ] Weather publishes `LocationSearched` (query, location id, found, user id if logged in); weather does not import stats
- [ ] `app/services/stats/`: schema `stats`, table `search_events`, written by an event handler without slowing down the request
- [ ] `GET /api/v1/stats/popular?since=7d&country=CZ`: most searched places (anonymous, aggregated)
- [ ] `GET /api/v1/me/stats`: my top places, searches per day, my unresolved searches
- [ ] Indexes for the time-window queries; SQL with `GROUP BY`, `date_trunc`, window functions
- [ ] Frontend: statistics page with charts; "popular" chips on the search page

**CI additions:** import-linter contract "weather must not import stats"

---

## Phase 11 — Trip builder service
Branch: `phase-11-trips`

- [ ] `app/services/trips/`: schema `trips`, tables `trips` and `trip_stops`
- [ ] Constraints: `CHECK (end_date >= start_date)`, stops of one trip must not overlap (exclusion constraint, `btree_gist`), stop order unique per trip
- [ ] Create a trip with its stops in one transaction; add / move / remove stops
- [ ] `GET/POST/PATCH/DELETE /api/v1/me/trips…`, only the owner can see or change a trip
- [ ] `GET /api/v1/me/trips/{id}/forecast`: the weather for each stop on its own dates, fetched concurrently through `WeatherService` (and its cache)
- [ ] Stops more than 16 days ahead return "forecast available from <date>" instead of data
- [ ] Frontend: trip list, trip editor (stops, dates, order), trip forecast view

**CI additions:** none beyond new tests

---

## Phase 12 — My places + dashboard
Branch: `phase-12-places`

- [ ] In the weather service: table `weather.favourite_places` (user, location, position, nickname, `UNIQUE(user_id, location_id)`)
- [ ] `GET/POST/PATCH/DELETE /api/v1/me/places`
- [ ] `GET /api/v1/me/dashboard`: current weather for all my places, fetched concurrently (`asyncio.gather`)
- [ ] Frontend: dashboard page, "save place" button on the search page
- [ ] README and screenshots updated, `CHANGELOG.md`
- [ ] Tag `v2.0.0`

**CI additions:** none beyond new tests

---

## Optional extensions
- [ ] Deploy to GCP Cloud Run with Terraform (CI: `terraform fmt -check` + `terraform validate`)
- [ ] Rate limiting (Redis token bucket)
- [ ] Weather alerts: a scheduled worker checks user rules; events through **RabbitMQ** instead of the in-process bus
- [ ] gRPC interface alongside REST
- [ ] Prometheus metrics, OpenTelemetry tracing
- [ ] End-to-end browser tests (Playwright) against the `full` profile
