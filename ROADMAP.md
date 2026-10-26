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

- [x] Multi-stage `Dockerfile` for the API: Poetry installs into a virtualenv in a build stage → slim Python runtime stage, non-root user, `HEALTHCHECK` on `/health`
- [x] `.dockerignore` as an allow-list: only `app/`, `pyproject.toml` and `poetry.lock` reach the build (no tests, caches, `.git`, `.env`, `frontend/`)
- [x] `api` service in `docker-compose.yml` under the `full` profile, with `REDIS_URL=redis://redis:6379/0` and `depends_on: redis (healthy)`
- [x] `docker compose --profile full up` starts the whole basic app (api + redis); `docker compose up` still starts only the infrastructure
- [x] Image runs Uvicorn without `--reload`, settings only from environment variables
- [x] Host port configurable (`API_PORT`, default 8000)
- [x] `scripts/smoke_test.sh` + `poe smoke-test`: readiness, OpenAPI, a real weather request, the cache hit, the error format
- [x] README: development mode vs full stack

**CI additions:** new job `Docker image`: build the image (layer cache between runs) · start the `full` profile and wait for healthchecks · `scripts/smoke_test.sh` · container logs on failure · shut down. Required check in the ruleset.

---

## Phase 5 — Frontend (basic UI)
Branch: `phase-5-frontend`

A Vue 3 + TypeScript single-page app in `frontend/`, using only the public REST API (ARCHITECTURE.md §9).

**Setup**
- [x] `frontend/` with Vite, Vue 3, TypeScript (strict), Vue Router, ESLint + Prettier, Vitest + Vue Test Utils
- [x] API types generated from the backend's OpenAPI schema with `openapi-typescript` (`scripts/export_openapi.py` → `frontend/openapi.json` → `src/api/schema.d.ts`, `poe generate-api`); typed calls with `openapi-fetch`, every failure becomes an `ApiError` with the backend's error code
- [x] Dev server proxies `/api` to `localhost:8000` (no CORS setup needed)

**Pages and components**
- [x] Search page: city input → current weather card + 7-day forecast list; current weather, forecast and alternatives load in parallel, and a slow answer to an older search can never overwrite a newer one
- [x] The search lives in the URL (`/?city=Prague&country=CZ`): bookmarkable, shareable, back button works
- [x] Ambiguous names: "Not the place you meant? See N other places matching …" links to a places page (`/places?q=Odessa`) listing up to 20 matches from `/locations/search`; each entry opens exactly that place
- [x] Weather endpoints accept an optional `region` (`city=Odessa&country=US&region=Missouri`), so same-name places inside one country can be selected. With a region the name must match exactly, because the geocoder also returns fuzzy matches ("Saint Paris" for "Paris")
- [x] Location ids: `location.id` is the GeoNames id (stable, the same in every language); the weather endpoints accept `id`, and the places list links by id, so a link survives a language switch and even two places with the same name in the same region (Paris, Ohio, twice) are told apart
- [x] Postal codes and numbers are not looked up: the geocoder would match them as postcodes (`10001` → New York, `123` → a random postcode prefix). `city` / `q` must contain a letter (API: `422 VALIDATION_ERROR`; the form explains it before sending)
- [x] Only populated places: the geocoder also returns countries, dams, parks, airports. A country name ("Germany") answers `404 NOT_A_CITY` instead of the weather at the country's centre point or a town that only shares an old name (Germany → Camp Dennison, Ohio); the page explains it and links to the towns really called Germany. Providers implement one method, `GeocodingClient.find()`
- [x] Units toggle (metric / imperial), remembered in `localStorage`

**Languages:** English, Ukrainian, Czech, Russian
- [x] `vue-i18n`: messages in `src/i18n/locales/{en,uk,cs,ru}.json`, typed from `en.json` (a missing key fails `vue-tsc`), plural rules per language, dates through `Intl`; `<html lang>` follows the choice
- [x] Language picker in the header (each language in its own name); remembered in `localStorage`, the browser's language is the first default; switching reloads the page data in the new language
- [x] API parameter `lang` (`en` / `uk` / `cs` / `ru`) on the weather and search endpoints: place names, weather descriptions and unit labels in that language; place cache entries per language, weather entries shared by all languages
- [x] Names in any alphabet: without an exact match the name is retried in the other languages of the same alphabet, and places found that way are fetched by id in the interface language (`Київ` with an English interface → Kyiv, Ukraine; `Germany` with a Russian interface → `NOT_A_CITY`)
- [x] GeoNames provider (geopy) keeps its limits: names in English, lookup by `id` answers `501 NOT_SUPPORTED`
- [x] Loading, empty and error states mapped from the API error codes (`CITY_NOT_FOUND`, `NOT_A_CITY`, `UPSTREAM_TIMEOUT`, …)
- [x] Responsive layout (phone width up to desktop), light and dark colour scheme
- [x] Open-Meteo attribution in the footer (required by its CC BY 4.0 licence)

**Packaging**
- [x] Multi-stage `frontend/Dockerfile`: Node builds the static files → unprivileged nginx (non-root) serves them and proxies `/api`, `/health`, `/docs` to the `api` service; hashed assets cached for a year, `index.html` never cached, security headers
- [x] `web` service in the `full` profile: `docker compose --profile full up` → open http://localhost:8080

**Tests**
- [x] Vitest tests: API client (query building, error mapping, network failure), formatting, units storage, place links, i18n (same keys in every language, plural forms, language detection), and both pages through the real router with a mocked API module (search, URL, places list, ids, error messages, retry, units, languages, cached badge, stale responses)

**CI additions:** new job `Frontend`: **generated API types are up to date** (regenerate from the backend code and fail on a diff) · ESLint · Prettier · `vue-tsc` · Vitest · build. The `Docker image` job also builds the `web` image and the smoke test checks http://localhost:8080 (page, deep links, `/api` proxy). Required check in the ruleset.

---

## Phase 6 — Release 1.0
Branch: `phase-6-release`

- [x] Retries with `tenacity` in `get_json` for temporary upstream failures (timeouts, dropped connections, 5xx, 429): 3 attempts, exponential backoff with jitter, 8 s budget; other 4xx are never retried; each retry is logged
- [x] Structured logging with `structlog` (JSON in containers, readable locally), also for uvicorn's and httpx's log lines; our own code logs in one style, an event name plus fields (`upstream_retry`, `cache_unavailable`, ...); request id middleware: `X-Request-ID` in responses and on every log line of the request, created by nginx and written into its access log too
- [x] `LOG_LEVEL` and `LOG_FORMAT` settings
- [x] Successful health checks (`/health`, `/health/ready`) kept out of the access log; failing ones are logged
- [x] README: screenshots, quick start (`docker compose --profile full up`), API examples, logs, releases, links to the docs
- [x] `CHANGELOG.md`; versions set to 1.0.0 (`pyproject.toml`, the API, `frontend/package.json`; a test keeps the API and `pyproject.toml` in step)
- [ ] First release `v1.0.0` by hand after this phase is merged (README → Releases → First release); later releases come from release PRs

**CI additions:**
- [x] **Pull requests run only the jobs for the parts they change.** A first job, `Changes` (`dorny/paths-filter`), compares the PR branch with `main` and decides per job; the other jobs start only when their files changed:

  | Job | Runs when the PR changes |
  |-----|--------------------------|
  | `Lint, type-check, test` | `app/`, `tests/`, `scripts/`, `pyproject.toml`, `poetry.lock`, `*.md` (ruff also checks the Python examples in Markdown) |
  | `Redis integration` | `app/`, `tests/`, `pyproject.toml`, `poetry.lock` |
  | `Docker image` | `app/`, `frontend/`, `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `scripts/smoke_test.sh`, `pyproject.toml`, `poetry.lock` |
  | `Frontend` | `frontend/`, `app/` (a backend change can change the API contract this job checks), `scripts/export_openapi.py` |

  A change to `.github/workflows/` runs every job.
- [x] **Pushes to `main` (every merge) always run all jobs**, whatever changed.
- [x] **One required check, `CI result`.** It waits for all jobs and fails if any of them failed; skipped jobs count as passed. The ruleset then requires only this check, so a PR that skips jobs is not blocked by checks that never reported, and a new job needs no ruleset change.
- [x] On tag `v*.*.*` (`publish.yml`): check the tag against the versions in the code, build both images, smoke-test them, then push them to GitHub Container Registry (`<version>`, `<major>.<minor>`, `latest`); first CD step
- [x] Versions from Conventional Commits with **release-please**: `fix:` → patch, `feat:` → minor, `feat!:` / `BREAKING CHANGE:` → major, `Release-As:` for milestones, `chore:` & co. release nothing. Every merge updates one release PR (versions in all five files + `CHANGELOG.md`), which merges itself once its checks pass; that creates the tag, which publishes the images. From minor 50 on the release PR waits for a manual merge, with a comment suggesting to decide about a milestone release
- [x] `PR title` check (`amannn/action-semantic-pull-request`): with squash merging the title is the commit release-please reads
- [x] `scripts/export_openapi.py` writes whole-number floats like JavaScript (`16`, not `16.0`), so release-please's rewrite of `openapi.json` keeps the "API types up to date" check green

---

# Release 2.0: weather, trips and statistics

## Phase 7 — Restructure into core + services
Branch: `phase-7-restructure`

The code moves into the structure from ARCHITECTURE.md §6. **No behaviour change**: the existing tests prove the move is safe, and the API contract (OpenAPI schema) stays identical.

- [ ] `app/core/`: config, HTTP client + `get_json`, errors, shared exceptions
- [ ] `app/core/cache/`: `Cache` interface, `RedisCache` (the only module importing `redis`), and `get_or_load()`, the cache-aside logic moved out of `WeatherService` (a cache failure counts as a miss)
- [ ] `app/services/weather/`: router, service, schemas, `cache_keys.py` (key formats and TTLs: weather decisions, not core's), `providers/` (renamed from `clients/`: Open-Meteo, GeoNames)
- [ ] Tests mirror the new layout in the top-level `tests/` (ARCHITECTURE §11, §13): `tests/core/...` and `tests/services/<service>/{unit,api,integration}/`; shared `conftest.py`, `doubles.py`, `logs.py` and `fixtures/` stay at the top. Tests are not moved into `app/`: they would ship in the image and fall under the import rules
- [ ] Dependency rules written down as import-linter contracts in `pyproject.toml` (services → core only; no imports from core into services; `redis` imported only in `core/cache/redis.py`)

- [ ] Frontend grouped by feature (ARCHITECTURE.md §9.1): `src/shared/` (API client, i18n, router, common components) and `src/features/weather/`; tests in `frontend/tests/<feature>/`. Folders for `auth`, `trips` and `stats` come with their phases
- [ ] Frontend import rules with ESLint's `no-restricted-imports`: features use `shared`, `shared` imports no feature, features import each other only where allowed (`trips` → `weather`, `weather` → `stats`)

**CI additions:** new step `Architecture` (`lint-imports`) in the `Lint, type-check, test` job; the frontend import rules run in the `Frontend` job's existing lint step. The `Frontend` job's "API types up to date" check proves the contract did not change.

---

## Phase 8 — PostgreSQL foundation
Branch: `phase-8-postgres`

- [ ] `db` (dev, port 5432, persistent volume) and `db-test` (port 5433, tmpfs) as `postgres:16-alpine` in `docker-compose.yml`; `api` in the `full` profile depends on `db`
- [ ] `app/core/db.py`: SQLAlchemy 2.0 async engine + session dependency (`asyncpg`)
- [ ] Alembic with async support; one schema per service (ARCHITECTURE.md §8); first migration creates schema `weather`
- [ ] `weather.locations`: places stored once, keyed by the GeoNames id the API already returns as `location.id` (Phase 5), upserted from geocoding results (`INSERT … ON CONFLICT`)
- [ ] `GET /api/v1/locations/{id}`; lookups by id are served from the table before asking the provider
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
- [ ] Frontend (`features/auth/`): register / login / logout, user menu, preferences page
- [ ] Frontend: `GET /me` on start into a Pinia user store; `meta.requiresAuth` routes with a guard redirecting guests to `/login?next=…`; any `401` clears the store and redirects the same way
- [ ] Frontend: preferences from `localStorage` for guests; after login the saved ones from `/me` take over, changes go to `PATCH /me/preferences`

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
- [ ] Frontend (`features/stats/`): statistics page with charts; "popular" chips on the search page

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
- [ ] Frontend (`features/trips/`): trip list, trip editor (stops, dates, order), trip forecast view

**CI additions:** none beyond new tests

---

## Phase 12 — My places + dashboard
Branch: `phase-12-places`

- [ ] In the weather service: table `weather.favourite_places` (user, location, position, nickname, `UNIQUE(user_id, location_id)`)
- [ ] `GET/POST/PATCH/DELETE /api/v1/me/places`
- [ ] `GET /api/v1/me/dashboard`: current weather for all my places, fetched concurrently (`asyncio.gather`)
- [ ] Frontend (`features/weather/`): dashboard page, "save place" button on the search page
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
