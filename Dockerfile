# syntax=docker/dockerfile:1
#
# API image. Two stages:
#   builder: Poetry installs the runtime dependencies into /app/.venv
#   runtime: only Python, the virtualenv and the app code (no Poetry, no build tools)

ARG PYTHON_IMAGE=python:3.12.15-slim

# ---------------------------------------------------------------------------- builder
FROM ${PYTHON_IMAGE} AS builder

ENV POETRY_VERSION=2.5.1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry-cache \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# Dependencies first: this layer is rebuilt only when the lock file changes,
# not on every code change.
COPY pyproject.toml poetry.lock ./
RUN --mount=type=cache,target=/tmp/poetry-cache \
    poetry install --only main --no-root

# ---------------------------------------------------------------------------- runtime
FROM ${PYTHON_IMAGE} AS runtime

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=prod \
    LOG_FORMAT=json

# Never run as root inside the container.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY app ./app

USER app
EXPOSE 8000

# Liveness only: /health does not depend on Redis, so a cache outage does not
# make the container "unhealthy" (readiness is /health/ready).
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

# No --reload: that is for development only. --proxy-headers: trust X-Forwarded-*
# from the reverse proxy (nginx in front of the API from Phase 5).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
