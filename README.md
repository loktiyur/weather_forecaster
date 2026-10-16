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

## Checks

The same checks run in CI on every pull request. Run them before pushing:

```bash
poetry run ruff check .            # lint
poetry run ruff format --check .   # formatting (drop --check to auto-format)
poetry run mypy                    # static type checking (strict)
poetry run pytest                  # tests (add -v to see each test)
```

Run all pre-commit hooks on the whole repository at once:

```bash
poetry run pre-commit run --all-files
```
