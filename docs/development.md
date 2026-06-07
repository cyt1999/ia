# Development Guide

This project uses `uv` for Python dependency and virtual environment management.

## Install uv

Follow the official installer for your system:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then verify:

```bash
uv --version
```

## Create The Environment

```bash
uv sync
```

This creates `.venv/` and installs dependencies from `pyproject.toml`. When `uv.lock` exists, `uv sync` installs the locked versions.

## Add Dependencies

Runtime dependency:

```bash
uv add fastapi
```

Development dependency:

```bash
uv add --dev pytest
```

## Configure Environment

```bash
cp .env.example .env
```

Fill in DeepSeek and Feishu values in `.env`. Do not commit `.env`.

`FEISHU_EVENT_MODE=long_connection` is the default. In this mode the app uses the official Feishu Python SDK WebSocket connection and does not need a public event subscription URL. Set `FEISHU_EVENT_MODE=webhook` only if you intentionally want to use the HTTP webhook fallback.

## Run The App Locally

```bash
uv run uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/healthz
```

## Database Migrations

Apply migrations:

```bash
uv run alembic upgrade head
```

Create a new migration after model changes:

```bash
uv run alembic revision --autogenerate -m "describe change"
```

## Tests

```bash
uv run pytest
```

## Architecture And Debugging

- Agent architecture notes: `docs/agent-architecture.md`
- Layered debugging guide: `docs/debugging.md`

## Docker Compose

```bash
docker compose up --build
```

SQLite data is stored under `./data` by default.
