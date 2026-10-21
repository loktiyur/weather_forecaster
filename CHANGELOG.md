# Changelog

All notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-20

The basic weather app: a REST API and a web frontend, packaged as two Docker images.

### Added

**Web app**
- Search a city and see the current weather and a 7-day forecast; the search is part of the
  URL, so it can be bookmarked and shared.
- "Not the place you meant?" opens a list of every place matching the name (Odessa, Texas
  instead of Odesa, Ukraine); each entry opens exactly that place.
- Interface in English, Ukrainian, Czech and Russian, chosen in the header and remembered;
  place names, weather descriptions, units and dates follow the language. A city can be typed
  in Latin or Cyrillic whatever the interface language.
- °C / °F toggle, light and dark colour scheme, layout from phone width to desktop.
- A clear message for every error, with "Try again" for temporary problems.

**REST API** (`/api/v1`, documented at `/docs`)
- `GET /weather/current` and `GET /weather/forecast` by `city` (+ `country`, `region`) or by
  place `id`, in `lang` = `en` / `uk` / `cs` / `ru`, in metric or imperial units.
- `GET /locations/search`: populated places matching a name, with stable GeoNames ids.
- `GET /health` (liveness) and `GET /health/ready` (readiness, checks Redis).
- One error format for every error, with a code per situation (`CITY_NOT_FOUND`,
  `NOT_A_CITY`, `UPSTREAM_TIMEOUT`, ...). Names without letters (postal codes) and country
  names are rejected with an explanation instead of returning a random place.
- Redis cache (cache-aside) for places and weather, with `Cache-Control` headers; the API keeps
  working without Redis.
- Temporary failures of Open-Meteo (timeouts, 5xx, 429) are retried with backoff (tenacity).
- Structured logs (structlog): readable lines locally, JSON in the container; events with named
  fields (`request`, `upstream_retry`, `cache_unavailable`, ...); every line of a request carries
  its `X-Request-ID`, which nginx sets and the API returns. Successful health
  checks are not logged.
- Geocoding through Open-Meteo by default; GeoNames (geopy) as an alternative provider.

**Delivery**
- Docker images for the API (Python, non-root) and the web app (nginx, non-root);
  `docker compose --profile full up` runs the whole app.
- CI on every pull request: lint, format, types (mypy strict, vue-tsc), unit, API, Redis
  integration and frontend tests, a coverage gate, a check that the frontend's API types match
  the backend, and a smoke test of both images. Pull requests run only the jobs for the parts
  they change; one `CI result` check guards merging.
- Releases from Conventional Commits (release-please): `fix:` → patch, `feat:` → minor,
  `feat!:` → major, through a release PR; its tag publishes both images to GitHub Container
  Registry after a smoke test. A `PR title` check keeps titles in that format.

[1.0.0]: https://github.com/loktiyur/weather_forecaster/releases/tag/v1.0.0
