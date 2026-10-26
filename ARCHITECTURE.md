# Weather Forecaster — Architecture

A weather app built like a production system: an async FastAPI backend, a Vue frontend, Redis caching, Docker and a CI pipeline that guards every change. It grows in two releases:

| Release | What the user gets | Status |
|---------|--------------------|--------|
| **1.0: basic weather app** | Type a city → current weather and a daily forecast, ambiguous names resolved, metric / imperial | Backend done (Phases 0–3); Docker and frontend in Phases 4–6 |
| **2.0: weather, trips and statistics** | Accounts, a trip builder showing the weather for every stop, saved places with a dashboard, statistics about searches | Phases 7–12 |

Every section below is marked **v1.0** (exists or is part of the basic release) or **v2.0** (target of the second release). Phases and progress: [ROADMAP.md](ROADMAP.md).

The goal of the project is to show understanding of **API design**, of the **popular Python backend stack** and of **architecture decisions**. Where there was a real choice, this document says what was chosen and why.

---

## 1. Requirements

### Functional

| # | Requirement | Release |
|---|-------------|---------|
| F1 | The user enters a city name and gets the current weather (temperature, feels-like, humidity, wind, description). | v1.0 |
| F2 | The user can see a daily forecast for 1–16 days (min/max temperature, humidity, sunrise/sunset). | v1.0 |
| F3 | Ambiguous names are handled: the user sees *which* place was used and can pick another one (e.g. Paris, France vs Paris, Texas). | v1.0 |
| F4 | A web page lets the user do all of the above without tools like curl. | v1.0 |
| F5 | Users can register, log in and set preferences (units, language, home place). | v2.0 |
| F6 | Users can build trips from stops (place + dates) and see the weather for every stop on its own dates. | v2.0 |
| F7 | Users can save places and see the current weather for all of them on a dashboard. | v2.0 |
| F8 | Users see statistics about their searches; everyone sees the most popular places. | v2.0 |

### Non-functional

| # | Requirement |
|---|-------------|
| N1 | Fully async I/O: no blocking calls inside the event loop. |
| N2 | Upstream calls are cached (Redis) to stay fast and respect the free API limits. A cache outage makes the app slower, never broken. |
| N3 | Clear, consistent error responses (one JSON format for every error). |
| N4 | Configuration via environment variables only; no secrets in code or in the repository. |
| N5 | Tested without calling external APIs; real Redis/Postgres in Docker for integration tests; every PR must pass CI. |
| N6 | The whole app starts with one command: `docker compose --profile full up`. |
| N7 | (v2.0) Module boundaries are enforced automatically in CI, not only described here. |

---

## 2. Tech stack

Widely used, well-maintained tools with a clear job each; the reason for every choice is in the tables.

### Backend

| Concern | Choice | Why | Release |
|---------|--------|-----|---------|
| Language | **Python 3.12** | Modern typing, fast asyncio | v1.0 |
| Web framework | **FastAPI** + **Uvicorn** | Async-first, OpenAPI generated from types, dependency injection | v1.0 |
| Validation | **Pydantic v2**, **pydantic-settings** | Request/response models, typed settings from env vars | v1.0 |
| HTTP client | **httpx** (`AsyncClient`) | Async, timeouts, connection pooling, easy to mock | v1.0 |
| Weather data | **Open-Meteo** Forecast + Geocoding APIs | Free, no API key | v1.0 |
| Alternative geocoder | **GeoNames** via `geopy` | Kept from the prototype; sync library run in a worker thread. geopy's client has no language option and no lookup by id: names come in English, `id` requests answer `501` | v1.0 |
| Cache | **Redis 7** + `redis.asyncio` | TTL cache, shared between processes | v1.0 |
| Retries | **tenacity** | Backoff for transient upstream errors | v1.0 (Phase 6) |
| Logging | **structlog** | Structured logs with a request id | v1.0 (Phase 6) |
| Database | **PostgreSQL 16**, one schema per service | Data we keep: users, trips, places, statistics | v2.0 |
| ORM / migrations | **SQLAlchemy 2.0 async** + **asyncpg**, **Alembic** | Typed models, async sessions, versioned schema changes | v2.0 |
| Auth | **PyJWT**, **pwdlib** (Argon2) | JWT in an httpOnly cookie, modern password hashing | v2.0 |
| Architecture checks | **import-linter** | Module dependency rules enforced in CI | v2.0 |

### Frontend

| Concern | Choice | Why |
|---------|--------|-----|
| Framework | **Vue 3** (Composition API) + **TypeScript** (strict) | Component-based, typed; fits interactive pages like the trip editor |
| Build / dev server | **Vite** | Fast dev server with an `/api` proxy, small production builds |
| Routing / state | **Vue Router**, **Pinia** (from v2.0, for the logged-in user) | Standard Vue tooling |
| Languages | **vue-i18n** (Composition API) | The standard Vue i18n library: messages per language, plural rules, typed message keys |
| API client | **openapi-typescript** + **openapi-fetch** | Types generated from the backend's OpenAPI schema: the contract is checked at compile time |
| Quality | **ESLint**, **Prettier**, **vue-tsc**, **Vitest** + Vue Test Utils | Lint, type check, component tests |
| Serving | **nginx** (in the `web` image) | Serves the built files, proxies `/api` to the backend |

### Tooling and delivery

| Concern | Choice |
|---------|--------|
| Dependencies | **Poetry** (backend), **npm** (frontend) |
| Tasks | **poethepoet** (`poe check`, `poe test-unit`, …) |
| Code quality | **ruff**, **mypy** (strict), **pre-commit** |
| Testing | **pytest**, **pytest-asyncio**, **respx**, `httpx.ASGITransport`, real Redis/Postgres in Docker |
| Containers | **Docker** (multi-stage images) + **docker compose** (profiles) |
| CI/CD | **GitHub Actions**, images pushed to **GitHub Container Registry** on release tags |
| Deploy (optional) | **GCP Cloud Run** + Memorystore + Cloud SQL, provisioned with **Terraform** |

> **Not used on purpose:** `pandas` (an API returns JSON, Pydantic models are the right shape), fakeredis (real Redis in Docker instead). gRPC and RabbitMQ are listed as extensions (§15), where they would have a real job.

---

## 3. Architecture style: modular monolith

**One deployable backend and one database, divided inside into services with strict, one-way dependencies.**

- **One deployable unit.** The backend is one image, one process and one migration history. Services talk to each other through ordinary function calls: no network hops between them, no partial failures between parts of the same request, and a single database transaction can cover a whole operation (e.g. creating a trip with all its stops).
- **Services are real boundaries.** Each service (weather, trips, stats) owns its code folder, its database schema and its endpoints. Other services reach it only through its service class, so its tables and internals can change without touching anyone else.
- **Dependencies point one way.** Everything may use `core`; `trips` may use `weather`; `weather` knows nothing about `trips` or `stats`. A service can therefore be understood, tested and changed on its own, and the code cannot slowly turn into a web where everything imports everything.
- **Shared relational data stays consistent.** Trips, saved places and statistics all refer to the same users and places. In one database these links are foreign keys and joins, so the database itself guarantees that no trip points at a place or user that does not exist.
- **Events where independence matters.** Statistics are fed by events (`LocationSearched`) instead of direct calls. Weather never waits for statistics and keeps working if the stats service is slow or broken.
- **Enforced, not only documented.** The dependency rules (§6) are import-linter contracts checked in CI; a forbidden import fails the pipeline.
- **Room to grow.** Because each service already has its own schema and a narrow interface, any of them could later be moved into its own deployment, and the event bus is the single place where a message broker would plug in.

---

## 4. System overview

### Full stack (v1.0): `docker compose --profile full up`

```mermaid
flowchart LR
    user([Browser])

    subgraph compose["docker compose --profile full"]
        web["web<br/>nginx: Vue app<br/>port 8080"]
        api["api<br/>FastAPI + Uvicorn"]
        redis[("redis<br/>cache")]
    end

    geo[[Open-Meteo<br/>Geocoding API]]
    meteo[[Open-Meteo<br/>Forecast API]]

    user -- "GET /" --> web
    user -- "GET /api/v1/..." --> web
    web -- "proxy /api" --> api
    api <--> redis
    api -- httpx --> geo
    api -- httpx --> meteo
```

The browser only talks to `web`. nginx serves the Vue app and forwards `/api/...` to the `api` container, so frontend and API share one origin (no CORS).

### Full stack (v2.0): the final architecture

```mermaid
flowchart LR
    user([Browser])

    subgraph compose["docker compose --profile full"]
        web["web<br/>nginx: Vue app<br/>features: weather · auth · trips · stats<br/>port 8080"]

        subgraph api["api: FastAPI + Uvicorn, one process"]
            direction TB
            trips["services/trips"]
            weather["services/weather"]
            stats["services/stats"]
            core["core<br/>config · auth · cache · db · http · errors · events"]
        end

        redis[("redis<br/>cache")]
        db[("db<br/>PostgreSQL<br/>schemas: auth · weather · trips · stats")]
    end

    geo[[Open-Meteo<br/>Geocoding API]]
    meteo[[Open-Meteo<br/>Forecast API]]

    user -- "GET /" --> web
    user -- "GET /api/v1/... + login cookie" --> web
    web -- "proxy /api" --> api
    trips -- "calls WeatherService" --> weather
    weather -. "event LocationSearched" .-> stats
    trips --> core
    weather --> core
    stats --> core
    core <--> redis
    core <--> db
    core -- httpx --> geo
    core -- httpx --> meteo
```

The outside stays as in v1.0: the browser talks only to `web`, nginx forwards `/api/...` to `api`, and the login cookie travels on the same origin. What changes is inside:

- **`api` is still one image and one process**, now divided into `core` and three services (§6). `trips` calls `weather` directly; `weather` tells `stats` about searches through an in-process event; all of them reach Redis, Postgres and Open-Meteo only through `core`.
- **`db` is new**: one PostgreSQL database with one schema per part (§8.2). Migrations run when the `api` container starts.
- **`redis` stays a disposable cache**: losing it slows requests down, nothing else.
- **`web` is grouped by feature** like the backend (§9.1), but it never sees the backend's parts: only the REST API.

### Development mode

```mermaid
flowchart LR
    user([Browser])

    subgraph host[Host machine]
        vite["Vite dev server<br/>npm run dev<br/>port 5173"]
        uvicorn["FastAPI<br/>poetry run uvicorn --reload<br/>port 8000"]
        tests[pytest]
    end

    subgraph compose["docker compose up -d"]
        redis[("redis<br/>port 6379")]
        redistest[("redis-test<br/>port 6380")]
    end

    user --> vite
    vite -- "proxy /api" --> uvicorn
    uvicorn <--> redis
    tests -. integration tests .-> redistest
```

Both apps run on the host and reload on save; Docker runs only the infrastructure. From v2.0 Compose also runs `db` (port 5432) and `db-test` (port 5433).

### Runtime setups

| Setup | Command | Backend runs | Containers |
|-------|---------|--------------|------------|
| **Development** | `docker compose up -d` + `poetry run uvicorn app.main:app --reload` + `npm run dev` | On the host | `redis`, `redis-test` (+ `db`, `db-test` in v2.0) |
| **Unit + API tests** | `poetry run poe test-unit` | In-process (ASGI transport) | None |
| **Integration tests** | `poetry run poe test-integration` | In-process | `redis-test` (+ `db-test` in v2.0); tests fail if they are not running |
| **Frontend tests** | `npm run test` (in `frontend/`) | Not needed (API client mocked) | None |
| **Full stack** | `docker compose --profile full up` | `api` container | `web`, `api`, `redis` (+ `db` in v2.0) |
| **CI** | GitHub Actions (§13) | In-process for tests; images built and smoke-tested | Service containers |
| **Production** (optional) | Terraform + Cloud Run | Cloud Run | Managed Redis and Postgres |

---

## 5. Backend today (after Phase 7)

The §6 layout with only the parts that exist so far. `core/db.py`, `core/events.py`, `core/auth/` and the `trips` and `stats` services are added in the phases that need them (ROADMAP.md).

```
app/
├── main.py                  # composition root: the lifespan creates the HTTP client, Redis and
│                            #   WeatherService; includes the routers
├── core/                    # infrastructure, no features
│   ├── config.py            # Settings
│   ├── cache/               # base.py (Cache), redis.py (RedisCache), aside.py (get_or_load)
│   ├── http.py              # shared httpx client + get_json (with retries)
│   ├── errors.py            # the error format, shared exception handlers, error_docs()
│   ├── exceptions.py        # shared exceptions (upstream failures)
│   ├── health.py            # /health, /health/ready (asks the cache directly)
│   ├── language.py          # Language: en / uk / cs / ru
│   ├── logging.py           # structlog setup
│   └── middleware.py        # request id + access log
└── services/
    └── weather/
        ├── router.py        # /weather/*, /locations/*
        ├── queries.py       # query parameter models
        ├── dependencies.py  # WeatherServiceDep
        ├── service.py       # WeatherService: geocode → weather, through the cache
        ├── cache_keys.py    # key layout and TTLs
        ├── errors.py        # CityNotFoundError, NotACityError, ... and their HTTP mapping
        ├── schemas.py       # Location and weather models: the API contract
        ├── weather_codes.py # WMO codes in four languages
        └── providers/       # Open-Meteo and GeoNames clients
```

| Layer | Knows about | Does **not** know about |
|-------|-------------|-------------------------|
| **Router** (`router.py`, `queries.py`) | HTTP: paths, query params, status codes, headers | Upstream URLs, Redis |
| **Service** (`service.py`, `cache_keys.py`) | The flow: cache → geocode → cache → weather; what is cached for how long | HTTP requests/responses |
| **Providers** (`providers/`) | One external API each: URL, params, JSON → model | Caching, callers |
| **Cache** (`core/cache`) | Redis commands, expiry on write, cache-aside | Which data is cached for how long |

Every dependency (HTTP client, Redis, settings, the service) is created once in the FastAPI **lifespan** and injected with `Depends(...)`, so tests can replace any of them. `WeatherService` depends on interfaces (`GeocodingClient`, `WeatherClient`, `Cache`), not on concrete classes.

Until Phase 7 the code was grouped by kind (`api/`, `clients/`, `cache/`, `schemas/`); the move changed no behaviour, and the OpenAPI schema stayed byte-for-byte the same.

---

## 6. Backend structure (v2.0): core + three services

```
app/
├── main.py                  # creates the app, includes the routers of core/auth and the 3 services
├── core/                    # infrastructure only: no features
│   ├── config.py            # Settings
│   ├── language.py          # Language: en / uk / cs / ru
│   ├── db.py                # Postgres: async engine, session dependency, Base
│   ├── cache/               # caching mechanism only: knows nothing about weather
│   │   ├── base.py          #   Cache interface (get/set/ping), CacheUnavailableError
│   │   ├── redis.py         #   RedisCache: the only module that imports redis
│   │   └── aside.py         #   get_or_load(): generic cache-aside, a cache failure = a miss
│   ├── http.py              # shared httpx client + get_json
│   ├── errors.py            # unified error format, shared exception handlers
│   ├── exceptions.py        # shared exceptions (upstream failures)
│   ├── health.py            # /health, /health/ready
│   ├── logging.py · middleware.py   # structlog setup; request id + access log
│   ├── events.py            # tiny in-process publish/subscribe
│   └── auth/                # users, register/login, JWT cookie, current_user dependency
│
└── services/
    ├── weather/             # 1. the weather engine
    │   ├── router.py        #    /weather/*, /locations/*, /me/places, /me/dashboard
    │   ├── service.py       #    WeatherService: what to cache, via core/cache get_or_load()
    │   ├── cache_keys.py    #    geo:/place:/weather: keys and their TTLs
    │   ├── errors.py        #    its exceptions and their HTTP mapping
    │   ├── places.py        #    "My places" + dashboard
    │   ├── providers/       #    Open-Meteo, GeoNames (renamed from clients/)
    │   ├── repository.py    #    SQL: locations, favourite_places
    │   ├── models.py        #    SQLAlchemy models
    │   └── schemas.py       #    Pydantic models
    │
    ├── trips/               # 2. the trip builder
    │   ├── router.py        #    /me/trips/*
    │   ├── service.py       #    TripService
    │   ├── repository.py    #    SQL: trips, trip_stops
    │   ├── models.py
    │   └── schemas.py
    │
    └── stats/               # 3. statistics
        ├── router.py        #    /stats/popular, /me/stats
        ├── service.py       #    StatsService + event handler
        ├── repository.py    #    SQL: search_events (GROUP BY, time windows)
        ├── models.py
        └── schemas.py
```

Every service has the same layers: **router** (HTTP) → **service** (logic, the only thing other services may call) → **repository** (SQL) → **models** (tables).

### What each part owns

| Part | Responsibility | Tables (schema) |
|------|----------------|-----------------|
| **core** | Infrastructure every service uses: config, DB session, the cache mechanism (interface, Redis adapter, cache-aside), HTTP, errors, events | none |
| **core/auth** | Who is calling: users, passwords, login cookie, preferences | `auth.users` |
| **weather** | Places and weather: geocoding, stored places, saved places, dashboard; which of its data is cached, under which keys, for how long | `weather.locations`, `weather.favourite_places` |
| **trips** | Trips made of stops (place + dates) and the weather for each stop | `trips.trips`, `trips.trip_stops` |
| **stats** | Search events and statistics | `stats.search_events` |

Login is not a service: it is infrastructure that all services need, like the database connection, so it lives in `core`. Saved places belong to `weather`: a saved place is "a location I want weather for", and the dashboard is "current weather for my places".

The cache is not a service either: it has no endpoints, tables or rules of its own, only `get`, `set` and `ping`. Its knowledge is split by who owns it:

- **`core/cache` owns the mechanism**: the `Cache` interface, the Redis adapter, and `get_or_load(cache, key, ttl, load)`: read the key → on a miss call `load` → store the result; a cache error is logged and counts as a miss, so a service never handles Redis failures itself. Only `core/cache/redis.py` and the app startup in `main.py` know the cache is Redis; replacing it changes one module.
- **Each service owns its decisions**: what is cached, the key format and the TTL (`services/weather/cache_keys.py`: a forecast stays fresh for an hour because of how Open-Meteo updates, which is a weather fact). `trips` and `stats` can cache through the same helper without depending on `weather`.

### Dependency rules

```mermaid
flowchart TD
    trips[services/trips] --> weather[services/weather]
    trips --> core
    weather --> core
    stats[services/stats] --> core
    weather -. "publishes LocationSearched" .-> events((core/events))
    events -. delivers .-> stats
    core["core<br/>config · db · cache · http · errors · events · auth"]
```

1. **Services may use `core`; `core` never imports a service.**
2. **`trips` may call `weather`** through `WeatherService`. The trip builder cannot work without weather, so a direct dependency is honest.
3. **`weather` never imports `trips` or `stats`.** It tells the world about searches with an **event**; whoever is interested subscribes.
4. **`stats` is called by nobody.** It listens to events and answers its own endpoints.
5. **Services call each other only through the other service's `service.py`**, never its repository or tables.
6. **Only `core/cache/redis.py` imports `redis`.** Services depend on the `Cache` interface and `get_or_load()`, never on Redis.

These rules are import-linter contracts in `pyproject.toml`, checked by the `Architecture` step in CI. A forbidden import fails the pipeline.

### Communication

| From → to | How | Why |
|-----------|-----|-----|
| trips → weather | Direct call: `await weather_service.get_forecast(...)` | Trips needs the result to answer the request |
| weather → stats | Event: `await events.publish(LocationSearched(...))` | Weather must keep working if stats is slow, broken or switched off |
| any service → auth | Dependency: `user: CurrentUser` in the route | Standard FastAPI security dependency |

The event bus is in-process (a dictionary of handlers). If messaging between processes is ever needed (e.g. weather alerts), `publish` is the single place where **RabbitMQ** would plug in.

**The UI talks only to the REST API**, never to a service. It does not know the backend is split into `core` and services, so code can move between them without the frontend noticing, as long as the API stays the same (the generated types and their CI check guard that). One page may use endpoints of several services, but the backend does the coordination: a trip forecast is one call, and `trips` asks `weather` for each stop. Details in §9.1.

---

## 7. Request flows

### Current weather (v1.0)

```mermaid
sequenceDiagram
    autonumber
    actor U as Browser
    participant R as Router
    participant S as WeatherService
    participant C as Redis
    participant G as Geocoding API
    participant W as Forecast API

    U->>R: GET /api/v1/weather/current?city=Prague
    R->>R: validate query (Pydantic)
    R->>S: get_current("Prague")

    S->>C: GET geo:en:prague:
    alt cache hit
        C-->>S: Location
    else cache miss
        S->>G: GET /v1/search?name=Prague&count=100
        G-->>S: results[0]
        S->>C: SET geo:en:prague: EX 604800
    end

    S->>C: GET weather:current:50.09:14.42:metric
    alt cache hit
        C-->>S: CurrentWeather
    else cache miss
        S->>W: GET /v1/forecast?latitude&longitude&current=...
        W-->>S: current block
        S->>C: SET weather:current:... EX 600
    end

    S-->>R: CurrentWeatherResponse (cached: true/false)
    R-->>U: 200 OK + Cache-Control: public, max-age=600
```

Errors are domain exceptions raised in the providers or the service (`CityNotFoundError`, `UpstreamServiceError`, `UpstreamTimeoutError`) and mapped to HTTP by exception handlers (§10). Redis errors are logged and treated as a cache miss.

### Trip forecast (v2.0)

```mermaid
sequenceDiagram
    autonumber
    actor U as Browser
    participant A as core/auth
    participant T as TripService
    participant DB as PostgreSQL
    participant W as WeatherService
    participant E as core/events
    participant St as stats

    U->>A: GET /api/v1/me/trips/7/forecast (cookie)
    A-->>T: current user
    T->>DB: trip 7 + stops + locations (JOIN), owned by the user?
    DB-->>T: 3 stops
    par for each stop, concurrently
        T->>W: get_forecast(location, dates)
        W->>W: Redis cache → Open-Meteo on a miss
        W-)E: publish LocationSearched
        E-)St: save search_event
    end
    T-->>U: each stop with the weather for its own dates
```

Stops more than 16 days ahead (the Open-Meteo forecast limit) get `"forecast available from <date>"` instead of data.

---

## 8. Data

### 8.1 Redis cache (v1.0)

| Key | Value | TTL |
|-----|-------|-----|
| `geo:{lang}:{normalized_city}:{country}[:{region}]` | `Location` JSON, names in `lang` | 7 days (places don't move) |
| `place:{id}:{lang}` | `Location` JSON (lookup by id) | 7 days |
| `weather:current:{lat:.2f}:{lon:.2f}:{units}` | `CurrentWeather` JSON | 10 min (Open-Meteo updates ~15 min) |
| `weather:forecast:{lat:.2f}:{lon:.2f}:{days}:{units}` | `list[DailyForecastDay]` JSON | 1 hour |

Coordinates are rounded to 2 decimals (~1 km) so nearby requests share an entry. City names are lower-cased and trimmed (`"  Prague "` and `"prague"` share `geo:en:prague:`). Weather entries have no language: descriptions and unit labels are translated when the response is built, so all four languages share one cached forecast.

- **Cache-aside** in `WeatherService` (from v2.0 the generic `get_or_load()` in `core/cache/aside.py`, §6): read the key → on a miss call the provider → store the result with its TTL. Values are Pydantic models serialised to JSON; an entry that no longer matches the model is treated as a miss. Errors such as `CityNotFoundError` are not cached.
- **Redis is optional at runtime.** Any cache error is logged and treated as a miss. `/health/ready` reports it with `503`.
- **HTTP caching:** responses carry `Cache-Control: public, max-age=<TTL>`, so browsers and proxies can reuse them too.
- **Redis is a disposable cache, never a data store.** It evicts keys under memory pressure (`allkeys-lru`) and may be flushed at any time. Anything that must be kept goes to PostgreSQL.

### 8.2 PostgreSQL (v2.0): one database, one schema per service

```
database "weather_app"
├── schema auth      ← core/auth
├── schema weather   ← services/weather
├── schema trips     ← services/trips
└── schema stats     ← services/stats
```

Each service owns its schema and only writes there, the same boundary as in the code. Because it is one database, foreign keys and joins across schemas still work, and there is one Alembic migration history. If a service ever had to move to its own database, its tables are already isolated.

Two separate databases (e.g. users / analytics) were considered and rejected: no foreign keys or joins between them, two migration histories, no transaction across both. That split pays off only at a scale this project does not have.

```mermaid
erDiagram
    AUTH_USERS ||--o{ WEATHER_FAVOURITE_PLACES : saves
    AUTH_USERS ||--o{ TRIPS_TRIPS : plans
    AUTH_USERS |o--o{ STATS_SEARCH_EVENTS : "optional"
    TRIPS_TRIPS ||--|{ TRIPS_TRIP_STOPS : has
    WEATHER_LOCATIONS ||--o{ WEATHER_FAVOURITE_PLACES : ""
    WEATHER_LOCATIONS ||--o{ TRIPS_TRIP_STOPS : ""
    WEATHER_LOCATIONS |o--o{ STATS_SEARCH_EVENTS : ""

    AUTH_USERS {
        uuid id PK
        text email UK
        text password_hash
        jsonb preferences "units, language, home place"
        timestamptz created_at
    }
    WEATHER_LOCATIONS {
        bigint id PK
        text provider_id UK "id from the geocoding provider"
        text name
        text country_code
        text region
        float latitude
        float longitude
        text timezone
    }
    WEATHER_FAVOURITE_PLACES {
        uuid user_id PK, FK
        bigint location_id PK, FK
        int position
        text nickname
    }
    TRIPS_TRIPS {
        uuid id PK
        uuid user_id FK
        text title
        timestamptz created_at
    }
    TRIPS_TRIP_STOPS {
        uuid id PK
        uuid trip_id FK
        bigint location_id FK
        int position
        date start_date
        date end_date
    }
    STATS_SEARCH_EVENTS {
        bigint id PK
        text query
        bigint location_id FK "null if not found"
        uuid user_id FK "null if anonymous"
        text endpoint
        bool found
        timestamptz created_at
    }
```

(Mermaid cannot show schemas, so names are written as `SCHEMA_TABLE`: `AUTH_USERS` is `auth.users`.)

### 8.3 Design decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Saved places | Table `weather.favourite_places` with `UNIQUE(user_id, location_id)` and FKs | Fixed shape, points at another table: the database guarantees no duplicates and no dangling ids, and "how many users saved Prague" is a plain `GROUP BY`. A JSONB array on the user would lose all of that |
| User preferences | `auth.users.preferences JSONB`, validated by a Pydantic model | Small, optional, belongs to the user, nothing references it, and new settings need no migration. The right job for JSONB |
| Places | Stored once in `weather.locations`, upserted from geocoding results | Stable ids for REST resources (`/locations/{id}`), and trips, saved places and statistics all reference the same row |
| Trip stops | `CHECK (end_date >= start_date)`, exclusion constraint against overlapping stops, unique position per trip | Invalid trips cannot exist, whatever the application code does |
| Search events | Written by an event handler, aggregated with SQL | Weather stays independent of statistics; statistics are flexible queries (time windows, per country) over raw events |

---

## 9. Frontend

A **separate application in the same repository** (`frontend/`), not part of the Python package and not a backend service. It is a client of the public REST API, just like Swagger or curl.

```
frontend/
├── openapi.json             # the backend's OpenAPI schema (exported by scripts/export_openapi.py)
├── src/
│   ├── main.ts · App.vue · router.ts   # the app shell: assembles the features (§9.1)
│   ├── shared/              # used by every feature
│   │   ├── api/
│   │   │   ├── schema.d.ts  # GENERATED from openapi.json, never edited by hand
│   │   │   └── client.ts    # typed openapi-fetch client; failures become ApiError(code)
│   │   ├── i18n/            # vue-i18n setup, plural rules, language detection; locales/{en,uk,cs,ru}.json
│   │   ├── components/      # ErrorBanner, LanguageSelect, UnitsToggle
│   │   ├── composables/     # useUnits
│   │   ├── query.ts         # reading values from the URL query
│   │   └── styles/
│   └── features/
│       └── weather/
│           ├── pages/       # SearchPage, PlacesPage
│           ├── components/  # CurrentWeatherCard, ForecastList, SearchForm
│           ├── composables/ # useWeatherLookup (parallel requests, stale-answer guard)
│           └── format.ts · places.ts   # display helpers (icons, local times, dates), place links
├── tests/                   # Vitest: shared/ (client, i18n, units), weather/ (helpers, the pages)
├── Dockerfile               # Node build stage → unprivileged nginx runtime stage
├── nginx.conf               # serve the app, proxy /api, /health, /docs to the api service
├── vite.config.ts           # dev proxy /api → http://localhost:8000
└── package.json
```

**The API is the contract.** The TypeScript types are generated from the OpenAPI schema FastAPI produces (`poe generate-api`). When a Pydantic model changes, the frontend type check shows every place that must follow, and CI regenerates the types from the backend code and fails if they differ from the committed ones. The backend and the frontend cannot drift apart unnoticed.

**The URL holds the search** (`/?city=Prague`, or `/?id=4401659&city=Odessa` for one exact place), so results can be bookmarked and shared and the back button works. Current weather, forecast and the number of other matching places are requested in parallel; only the newest search may update the page.

**Places, not countries (v1.0):** the geocoder also returns countries, dams, parks and airports. Providers keep only populated places. When the best match is a country ("Germany"), the weather endpoints answer `404 NOT_A_CITY`: the weather at a country's centre point says nothing about the country, and the next match is often a town that only shares an old name (Germany → Camp Dennison, Ohio). The page explains this and links to the towns that are really called Germany. `GeocodingClient.find()` is the one method a provider implements: it returns the populated places and the country the name means, if any; `search()` and `geocode()` are built on it.

**Ambiguous names (v1.0):** when the name matches other places, the page links to `/places?q=…`, which lists up to 20 matches. Each entry links to the place's **id**: `location.id` is the GeoNames id, stable and the same in every language, and the weather endpoints accept it as `id`. A link therefore still opens the same place after the language is switched, and even two places with the same name in the same region (Paris, Ohio, twice) are told apart. API clients without an id can still use name + country + `region`.

**Languages (v1.0):** the interface speaks English, Ukrainian, Czech and Russian.
- The frontend uses **vue-i18n**. Messages live in `src/i18n/locales/{en,uk,cs,ru}.json`; `en.json` defines their type, so a key missing in another language fails `vue-tsc`, and a test compares the key sets. Plural forms follow each language (1 місце, 2 місця, 5 місць). The choice is remembered in `localStorage`; the first default is the browser's language.
- Every API call sends `lang`. The backend returns place names, weather descriptions (`app/services/weather/weather_codes.py`, one tuple of four texts per code, so mypy rejects a missing language) and unit labels (`км/год`) in that language. Error messages stay English: they are for developers, and the frontend shows its own text per error code.
- **Names in any alphabet.** The geocoder matches a name only in the search language: "Київ" with `language=en` finds nothing, "Киев" with `language=uk` finds a village in Russia, and "Germany" with `language=ru` misses the country. So a result counts only when its best match is exactly the typed name; otherwise the name is retried in the other languages of the same alphabet (Ukrainian and Russian for Cyrillic, English and Czech for Latin). Places found that way are fetched again by id in the interface language, so typing "Київ" with an English interface shows "Kyiv, Ukraine". This logic lives in the `GeocodingClient` base class, so every provider gets it.

| | Development | Full stack / production |
|---|---|---|
| Frontend | `npm run dev` (Vite, port 5173, hot reload) | static files built by `npm run build`, served by nginx in the `web` image (port 8080) |
| API calls | Vite proxies `/api` → `localhost:8000` | nginx proxies `/api` → `api:8000` |
| Same origin | yes (proxy) | yes (proxy), so no CORS configuration |

### 9.1 Frontend in v2.0

**Its place does not change.** The frontend stays a client of the public REST API, served by nginx on the same origin. It sees endpoints, not the backend's `core` and services (§6): one page may use endpoints of several services, and when a result needs several parts, the backend combines them. The types for the new endpoints are generated from `openapi.json` like today, so the CI check covers them automatically.

| Page | Calls | Answered by |
|------|-------|-------------|
| Search (v1.0) + "popular" chips | `/weather/*`, `/locations/*`, `/stats/popular` | weather, stats |
| Places list (v1.0) | `/locations/search` | weather |
| Login, register, user menu | `/auth/*`, `GET /me` | core/auth |
| Preferences | `PATCH /me/preferences` | core/auth |
| Dashboard, "save place" | `/me/dashboard`, `/me/places` | weather |
| Trips, trip editor, trip forecast | `/me/trips/*` | trips (asks weather for each stop) |
| Statistics | `/stats/popular`, `/me/stats` | stats |

- **The UI does not feed the statistics.** A search is an ordinary weather call; the backend publishes `LocationSearched` itself. The UI only reads `/stats/*`.
- **Login.** The JWT is stored in an **httpOnly, Secure, SameSite=Lax cookie**. Page scripts cannot read it (protection against XSS), and because frontend and API share one origin the browser sends it automatically. On start the app calls `GET /me` and keeps the answer (the user or "guest") in a Pinia store. Routes that need login carry `meta: { requiresAuth: true }`; a router guard sends guests to `/login?next=<page>`, and after login the user returns there. Any `401` from the API clears the store and does the same redirect, so an expired session never leaves a half-working page.
- **Preferences.** A guest's language and units stay in `localStorage`, as in v1.0. After login, the saved preferences from `GET /me` take over, and every change is sent with `PATCH /me/preferences`, so they follow the user to another device.

**Code grouped by feature.** With six more pages, folders by type (`pages/`, `components/`, ...) mix every feature together. From Phase 7 the code is grouped like the backend:

```
frontend/src/
├── main.ts · App.vue · router.ts   # the app shell: the only code that imports every feature
├── shared/          # api client + generated types, i18n, common components (ErrorBanner, LanguageSelect, UnitsToggle)
└── features/
    ├── weather/     # search, places list, dashboard, "save place"
    ├── auth/        # login, register, preferences, the user store
    ├── trips/       # trip list, editor, trip forecast
    └── stats/       # statistics page, "popular" chips
```

Each feature folder holds its own `pages/`, `components/` and `composables/`; its tests are in `frontend/tests/<feature>/`, the tests of `shared` in `frontend/tests/shared/`. The router lives in the app shell, not in `shared`: it imports the pages of every feature, like `main.py` in the backend. The rules mirror the backend: every feature may use `shared`, and `shared` imports no feature (nor the app shell). Features use each other only where a page shows another feature's part: `trips` uses `weather` components (a forecast card per stop), and the `weather` search page shows the `stats` "popular" chips. Any other import between features is forbidden. ESLint's built-in `no-restricted-imports`, configured per feature folder in `eslint.config.js`, fails `npm run lint` on a forbidden import, the frontend counterpart of import-linter. Every folder in `src/features/` gets the rules automatically; the allowed imports between features are one list there (`ALLOWED_FEATURE_IMPORTS`), extended by the phase that adds a feature. Imports across folders use `@/...` (a `../` import is an error), so every import says where it points.

---

## 10. API design

Base path `/api/v1`. Interactive docs at `/docs` (Swagger) and `/redoc`.

### v1.0

| Method | Path | Query params | Description |
|--------|------|-------------|-------------|
| `GET` | `/api/v1/weather/current` | `city` (1–100 chars with a letter) **or** `id` (a `location.id`: exactly that place), `country` (ISO-2), `region` (picks one of several same-name places in a country), `lang` (`en` \| `uk` \| `cs` \| `ru`), `units` (`metric` \| `imperial`) | Current weather |
| `GET` | `/api/v1/weather/forecast` | same + `days` (1–16, default 7) | Daily forecast |
| `GET` | `/api/v1/locations/search` | `q`, `country`, `lang`, `limit` (1–20, default 5) | Candidate places for an ambiguous name, populated places only; `{"results": [...]}` |
| `GET` | `/health` | — | Liveness |
| `GET` | `/health/ready` | — | Readiness: Redis (and Postgres in v2.0) reachable, `503` otherwise |

### v2.0 additions

| Service | Endpoints |
|---------|-----------|
| core/auth | `POST /auth/register` · `POST /auth/login` · `POST /auth/logout` · `GET /me` · `PATCH /me/preferences` |
| weather | `GET /locations/{id}` · `GET/POST /me/places` · `PATCH/DELETE /me/places/{location_id}` · `GET /me/dashboard` |
| trips | `GET/POST /me/trips` · `GET/PATCH/DELETE /me/trips/{id}` · `POST/PATCH/DELETE /me/trips/{id}/stops…` · `GET /me/trips/{id}/forecast` |
| stats | `GET /stats/popular?since=7d&country=CZ` · `GET /me/stats` |

`/me/...` endpoints require login (`401` otherwise) and only ever return the caller's own data (`404` for someone else's trip, so ids of other users' trips are not revealed).

### Example response: `GET /api/v1/weather/current?city=Prague`

```json
{
  "location": {
    "id": 3067696,
    "name": "Prague",
    "country": "Czechia",
    "country_code": "CZ",
    "region": "Prague",
    "latitude": 50.08804,
    "longitude": 14.42076,
    "timezone": "Europe/Prague"
  },
  "current": {
    "time": "2026-10-16T14:00:00",
    "temperature": 12.4,
    "apparent_temperature": 10.9,
    "relative_humidity": 71,
    "wind_speed": 14.2,
    "weather_code": 3,
    "description": "Overcast",
    "is_day": true
  },
  "units": { "temperature": "°C", "wind_speed": "km/h" },
  "cached": false
}
```

`location.id` is the GeoNames id; from v2.0 it is also the key of the stored place (`weather.locations`).

### Error format

Every error has the same shape:

```json
{ "error": { "code": "CITY_NOT_FOUND", "message": "No place found for 'Pragu'." } }
```

Validation errors also list every invalid field:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters.",
    "details": [
      { "field": "days", "location": "query", "message": "Input should be less than or equal to 16" }
    ]
  }
}
```

| Situation | Exception | HTTP status |
|-----------|-----------|-------------|
| Invalid parameter | `RequestValidationError` | `422` |
| Unknown URL / wrong method | Starlette `HTTPException` | `404` / `405` |
| No place found | `CityNotFoundError` | `404` |
| The name is a country ("Germany") | `NotACityError` | `404` (`NOT_A_CITY`) |
| No populated place has this `id` | `LocationNotFoundError` | `404` (`LOCATION_NOT_FOUND`) |
| The provider cannot do it (GeoNames: lookup by `id`) | `NotSupportedError` | `501` (`NOT_SUPPORTED`) |
| Upstream 4xx/5xx or bad JSON | `UpstreamServiceError` (detail logged, generic message returned) | `502` |
| Upstream timeout | `UpstreamTimeoutError` | `504` |
| Not logged in (v2.0) | — | `401` |
| Constraint violated, e.g. overlapping stops (v2.0) | `ConflictError` | `409` |
| Redis down | logged, request continues without cache | `200` |

### Retries and logs (v1.0)

**Retries.** Every call to Open-Meteo goes through `get_json` (`app/core/http.py`), which retries temporary failures with **tenacity**: timeouts, dropped connections, HTTP 5xx and 429. At most 3 attempts with exponential backoff and jitter (~0.2 s, ~0.4 s), and a time budget of 8 s, so a user never waits for three full timeouts. Other 4xx answers ("Location ID not found") would come back the same and are never retried. After the last attempt the error is the same as without retries (`UPSTREAM_ERROR` / `UPSTREAM_TIMEOUT`). GeoNames calls go through geopy and are not retried.

**Logs.** `app/core/logging.py` configures **structlog** for our own log calls *and* for the standard library loggers of uvicorn and httpx, so every line has the same fields: `timestamp`, `level`, `logger`, `event` and any extra fields. Our code logs in one style only: `structlog.get_logger(__name__)` with a short event name and named fields (`log.warning("upstream_retry", service=..., attempt=2, status=503)`), so every detail is a field a log system can filter on, not words inside a sentence. Libraries keep their own message text; they reach the same handler through the standard library bridge. `LOG_FORMAT=json` (set in the API image) writes one JSON object per line for log systems; `text` writes readable lines for a terminal.

**Request id.** `RequestContextMiddleware` (`app/core/middleware.py`, a plain ASGI middleware) gives each request an id. It keeps the caller's `X-Request-ID` if it looks like an id, otherwise it generates one. It binds the id with `structlog.contextvars`, so every line written while the request is handled carries `request_id`, and it returns the id in the response header. nginx creates the id for requests from the browser and writes it into its own access log, so one id connects the nginx line, the API's access line and its calls to Open-Meteo. The middleware also writes the access log (method, path, query, status, duration); uvicorn's own access log is switched off, and successful health checks are left out, because Docker calls them every 10 s.

---

## 11. Project structure

### v1.0 (after Phase 6)

```
weather_forecaster/
├── app/                          # backend (layout in §5)
├── tests/
│   ├── fixtures/                 # recorded Open-Meteo responses
│   ├── unit/                     # providers, service, cache keys
│   ├── api/                      # endpoints via ASGITransport
│   └── integration/              # real Redis (redis-test); fail if Docker is down
├── frontend/                     # Vue app (layout in §9)
├── .github/workflows/ci.yml
├── scripts/
│   ├── smoke_test.sh             # end-to-end check of a running stack (CI + poe smoke-test)
│   └── export_openapi.py         # writes the API contract for the frontend (poe generate-api)
├── Dockerfile                    # api image
├── .dockerignore
├── docker-compose.yml            # redis, redis-test; profile full: api, web
├── pyproject.toml                # Poetry, ruff, mypy, pytest, poe tasks
├── .env.example
├── .pre-commit-config.yaml
├── ARCHITECTURE.md · ROADMAP.md · README.md · CHANGELOG.md
```

### v2.0 additions

```
├── app/                          # core + services (layout in §6)
├── migrations/                   # Alembic, one history for all schemas
├── frontend/src/                 # shared/ + features/{weather,auth,trips,stats}/ (§9.1)
├── tests/                        # outside app/: never in the image, not bound by the import rules
│   ├── conftest.py · doubles.py · logs.py · fixtures/   # shared by all tests
│   ├── core/                     # cache (aside, RedisCache), http, logging, events, auth, db
│   └── services/
│       ├── weather/
│       │   ├── unit/             # service logic, providers, cache keys
│       │   ├── api/              # endpoints with fake upstreams
│       │   └── integration/      # real Redis / Postgres
│       ├── trips/                # same three folders
│       └── stats/
└── docker-compose.yml            # + db, db-test
```

---

## 12. Configuration

All settings come from environment variables (`.env` locally, secrets manager in the cloud).

| Variable | Example | Purpose | Release |
|----------|---------|---------|---------|
| `APP_ENV` | `dev` | `dev` / `test` / `prod` | v1.0 |
| `GEOCODING_PROVIDER` | `open_meteo` | `open_meteo` or `geonames` | v1.0 |
| `GEONAMES_USERNAME` | `my_user` | only for `geonames` | v1.0 |
| `HTTP_TIMEOUT_SECONDS` | `5` | upstream timeout | v1.0 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis (`redis://redis:6379/0` inside compose) | v1.0 |
| `REDIS_TIMEOUT_SECONDS` | `0.5` | give up on a slow Redis quickly | v1.0 |
| `CACHE_TTL_GEOCODING_SECONDS` / `_CURRENT_` / `_FORECAST_` | `604800` / `600` / `3600` | cache lifetimes | v1.0 |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` | v1.0 (Phase 6) |
| `LOG_FORMAT` | `text` | `text` (readable) or `json` (one object per line; the API image sets `json`) | v1.0 (Phase 6) |
| `TEST_REDIS_URL` | `redis://localhost:6380/0` | tests only | v1.0 |
| `DATABASE_URL` | `postgresql+asyncpg://weather:weather@localhost:5432/weather_app` | Postgres | v2.0 |
| `TEST_DATABASE_URL` | `…@localhost:5433/weather_app_test` | tests only | v2.0 |
| `JWT_SECRET` | (secret) | signs login tokens; never committed | v2.0 |
| `JWT_TTL_MINUTES` | `60` | login lifetime | v2.0 |
| `COOKIE_SECURE` | `true` | `false` only for local HTTP | v2.0 |

---

## 13. Testing and CI

| Level | What | Tools | Infrastructure |
|-------|------|-------|----------------|
| Unit | providers (params, JSON mapping, errors), service logic, cache keys | `respx`, JSON fixtures, test doubles of our own interfaces | none |
| API | status codes, schemas, error format, validation, headers, auth rules (v2.0) | `httpx.AsyncClient` + `ASGITransport`, `dependency_overrides` | none |
| Integration: Redis | `RedisCache`, TTL expiry, full request path through Redis | `@pytest.mark.integration` | `redis-test` / CI service container |
| Integration: Postgres (v2.0) | repositories, constraints, migrations, statistics queries | `@pytest.mark.integration` | `db-test` / CI service container |
| Frontend | components, pages, API error handling | Vitest + Vue Test Utils, mocked API client | none |
| End-to-end (optional) | browser through the `full` profile | Playwright | full stack |

**Rules:**
- **One `tests/` folder, grouped by part, then by kind** (§11): all tests of a service are in `tests/services/<service>/`, split into `unit/`, `api/` and `integration/`. Tests stay outside `app/`, so they never reach the API image, the import-linter contracts cover only production code, and the shared doubles and fixtures live in one place. `pytest tests/services/weather` runs everything for one service.
- **No fakes of third-party infrastructure.** Redis and Postgres are tested for real; test doubles exist only for *our own* interfaces.
- **No test calls an external API.** Open-Meteo and GeoNames are always mocked.
- **Integration tests fail when their container is not running**, with a hint how to start it. A green run always means the real infrastructure was used.
- **Coverage gate:** ≥ 80 % over the whole backend suite.

### CI jobs

Pull requests run only the jobs whose files changed; pushes to `main` (every merge) run all of them. The `main` ruleset requires `CI result`, which reports for all CI jobs (a skipped job never reports a status of its own), and `PR title`.

| Job | Steps | From |
|-----|-------|------|
| `Lint, type-check, test` | ruff, format check, mypy strict, `Architecture` (import-linter, from Phase 7), unit + API tests | Phase 0 |
| `Redis integration` | `redis:7.4-alpine` service container, integration tests | Phase 3 |
| `Docker image` | build the `api` (and `web` from Phase 5) images, start the `full` profile, run `scripts/smoke_test.sh`: readiness, a real weather request, the cache hit, the error format (and the web page from Phase 5) | Phase 4 |
| `Frontend` | generated API types match the backend code, ESLint, Prettier, `vue-tsc`, Vitest, build | Phase 5 |
| `Postgres integration` | `postgres:16-alpine` service container, `alembic upgrade head`, `alembic check`, Postgres integration tests | Phase 8 |
| `Coverage` | merges coverage from the test jobs, applies the 80 % gate (until Phase 8 the gate runs in `Redis integration`) | Phase 8 |
| `Changes` | decides per job whether a pull request needs it (`dorny/paths-filter`); pushes to `main` run everything | Phase 6 |
| `CI result` | the only required check: fails if any job failed, skipped jobs count as passed | Phase 6 |
| `PR title` (`pr-title.yml`) | the PR title follows Conventional Commits (with squash merging it is the commit release-please reads) | Phase 6 |
| `Release PR` (`release.yml`, push to `main`) | release-please opens / updates the release PR (versions, `CHANGELOG.md`) and turns on its auto-merge (manual from minor 50); its merge creates the tag and GitHub Release | Phase 6 |
| `Publish images` (`publish.yml`, tag `v*.*.*`) | tag = versions in the code, build both images, smoke test, push them to GitHub Container Registry | Phase 6 |

```mermaid
flowchart LR
    pr([pull request])
    pr --> changes["Changes<br/>which parts changed?"]
    changes --> checks["Lint, type-check, test"]
    changes --> redisj["Redis integration"]
    changes --> docker["Docker image"]
    changes --> fe["Frontend"]
    changes --> pg["Postgres integration (v2.0)"]
    redisj --> cov["Coverage (v2.0)"]
    pg --> cov
    checks --> gate{"CI result<br/>nothing failed?"}
    docker --> gate
    fe --> gate
    cov --> gate
    redisj --> gate
    gate -- yes --> merge([merge allowed])
```

Service containers are official images started by GitHub next to the job; only the app's own images are built.

---

## 14. Deployment

```mermaid
flowchart LR
    tag([git tag v1.0.0]) --> gha[GitHub Actions]
    gha --> ghcr[(GitHub Container Registry<br/>api + web images)]
    ghcr --> compose["any Docker host<br/>docker compose --profile full up"]
    ghcr -. optional .-> run["Cloud Run<br/>api + web"]
    run -.-> mem[(Memorystore Redis)]
    run -.-> sql[(Cloud SQL Postgres, v2.0)]
    tf[Terraform] -. provisions .-> run & mem & sql
```

- **Release 1.0** is a set of two images (`api`, `web`) plus the official Redis image. `docker compose --profile full up` runs the whole app anywhere Docker runs.
- **Release 2.0** adds Postgres; migrations run when the `api` container starts.
- **Cloud deployment** (Cloud Run, managed Redis and Postgres, Terraform) is an optional extension.

---

## 15. Possible extensions

- **Weather alerts**: users define rules ("below 0 °C in Prague"); a scheduled worker checks them and publishes events through **RabbitMQ** instead of the in-process bus.
- **Climate comparison**: import history from the Open-Meteo Historical API and show "today is 6 °C warmer than the 10-year average".
- **Rate limiting** per user / IP with a Redis token bucket.
- **gRPC interface** alongside REST to show both API styles.
- **Observability**: Prometheus metrics, OpenTelemetry tracing.
- **End-to-end tests** with Playwright against the `full` profile.
