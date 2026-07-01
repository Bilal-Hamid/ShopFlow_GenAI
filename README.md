# ShopFlow

Monorepo for the ShopFlow GenAI upskilling project.

- [`backend/`](backend/) — REST API (Domain 1: Backend Engineering)
- `frontend/` — Next.js storefront + merchant admin (Domain 2: Frontend Engineering) — not yet started

## Stack choice: Backend

**Python 3.14 + FastAPI**, managed with **uv**, linted/formatted with **Ruff**.

FastAPI was chosen over Express/Fastify for automatic OpenAPI 3.1 generation (a graded
deliverable), native Pydantic-based validation, and async-first request handling. uv was chosen
as the dependency manager for its speed and single-lockfile workflow; Ruff replaces
Black/isort/Flake8 with one fast tool.

## Running locally (Docker)

```bash
cp .env.example .env      # adjust values if needed
docker compose up --build
```

This boots Postgres 16, Redis 7, and the API on `http://localhost:8000`. Check
`http://localhost:8000/health` once it's up.

## Backend: local development (without Docker)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14.

```bash
cd backend
uv sync                          # installs deps into .venv, including dev tools
cp .env.example .env             # point DATABASE_URL/REDIS_URL at your local db/redis
uv run uvicorn app.main:app --reload
```

The app validates required environment variables (`APP_ENV`, `DATABASE_URL`, `REDIS_URL`) at
startup via `backend/app/core/config.py` — it will refuse to boot rather than run with a missing
value.

## Backend: linting & formatting

```bash
cd backend
uv run ruff check .        # lint
uv run ruff format .       # format
```

## Backend: pre-commit

Hooks are configured at the repo root (`.pre-commit-config.yaml`) and run Ruff against
`backend/` on every commit. Install once from the repo root:

```bash
uv run --project backend pre-commit install
```
