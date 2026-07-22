# ShopFlow

Monorepo for the ShopFlow GenAI upskilling project.

- [`backend/`](backend/) — REST API (Domain 1: Backend Engineering) — **active**
- [`frontend/`](frontend/) — Next.js storefront + merchant admin (Domain 2: Frontend Engineering) — **foundation scaffolded**

## Stack choice: Backend

**Python 3.14 + FastAPI**, managed with **uv**, linted/formatted with **Ruff**. Async SQLAlchemy 2.0
(`asyncpg`) + Alembic for schema/migrations, Pydantic Settings for config, Redis for cart/tokens/rate
limiting, and Stripe for payments.

FastAPI was chosen over Express/Fastify for automatic OpenAPI 3.1 generation (a graded deliverable),
native Pydantic-based validation, and async-first request handling. uv was chosen as the dependency
manager for its speed and single-lockfile workflow; Ruff replaces Black/isort/Flake8 with one fast tool.

## What's implemented so far

The backend covers the full customer → merchant → admin flow plus payments:

- **Auth** — register / login / refresh / logout with JWT access + refresh tokens (see below).
- **RBAC** — role-based access control for `customer`, `merchant`, `admin`, enforced via a shared
  `require_roles(...)` dependency.
- **Catalog** — product CRUD, search/filter, categories (hierarchical), reviews (one per customer per
  product).
- **Cart** — Redis-backed cart per customer.
- **Orders** — checkout, listing, status transitions, and (mock) tracking.
- **Payments** — Stripe hosted Checkout on checkout, signature-verified webhook to confirm/cancel
  orders.
- **Merchant & admin** — dashboards, revenue summaries, user management, platform stats.
- **Cross-cutting** — RFC 7807 (`application/problem+json`) errors, cursor-based pagination
  (`nextCursor`), per-IP / per-user rate limiting, OpenAPI 3.1 spec.

### API surface

All routes are under `backend/app/api/routes/`. `GET /health` is the unauthenticated liveness check.
The interactive docs are served at `http://localhost:8000/docs` when the app is running.

| Group | Prefix | Highlights | Access |
| --- | --- | --- | --- |
| Auth | `/auth` | `register`, `login`, `refresh`, `logout` | public |
| Products | `/products` | list / search / get (public); create / update / delete | merchant / admin |
| Cart | `/cart` | get cart, add / update / remove items, empty | customer |
| Orders | `/orders` | `checkout`, list, get, `PATCH .../status`, `.../tracking` | authenticated |
| Reviews | `/products/{id}/reviews`, `/reviews` | list (public); create / edit / delete | customer / author / admin |
| Merchant | `/merchant` | dashboard, own products, own orders, revenue summary | merchant |
| Admin | `/admin` | users, orders, platform stats | admin |
| Webhooks | `/webhooks/payment` | Stripe events (verified by signature, not JWT) | Stripe only |

### Auth model

- Passwords hashed with **Argon2**.
- Two HS256 JWTs distinguished by a `type` claim: **access** (15 min default) and **refresh** (7 days
  default).
- Tokens are delivered **only via httpOnly cookies** — never in JSON bodies, never in localStorage.
  The access cookie is scoped to `/`; the refresh cookie is scoped to `/auth`.
- **Refresh-token rotation with reuse detection**: each login starts a token "family" tracked in Redis.
  Rotating consumes the old token; reusing a consumed token burns the whole family and forces re-login.
  Logout revokes the family.

### Payments (Stripe)

- On `POST /orders/checkout`, if `STRIPE_SECRET_KEY` is set, the API creates a hosted Checkout Session
  and returns its `payment_url`. The `order_id` is stamped in Stripe metadata.
- `POST /webhooks/payment` verifies the Stripe signature, dedupes by event id (Redis), and moves the
  order `pending → confirmed` on success or `pending → cancelled` (with restock) on failure. The paid
  amount is checked against the order total as a tamper guard.
- Payments are **optional**: with no `STRIPE_SECRET_KEY`, checkout still creates the order but
  `payment_url` is `null` and the order stays `pending`.

## Running locally (Docker)

From the repo root:

```bash
cp .env.example .env      # adjust values if needed (see "Environment variables" below)
docker compose up --build
```

This boots Postgres 16, Redis 7, and the API on `http://localhost:8000`. Check
`http://localhost:8000/health` once it's up, and browse the API at `http://localhost:8000/docs`.

## Backend: local development (without Docker)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14. You'll need a local Postgres 16 and Redis 7
(or point at the Docker ones).

```bash
cd backend
uv sync                          # installs deps into .venv, including dev tools
cp .env.example .env             # point DATABASE_URL/REDIS_URL at your local db/redis
uv run alembic upgrade head      # create the schema
uv run uvicorn app.main:app --reload
```

The app validates required environment variables at startup via `backend/app/core/config.py` — it
refuses to boot rather than run with a missing value. `DATABASE_URL` must use the
`postgresql+asyncpg://` scheme (async SQLAlchemy + Alembic).

## Environment variables

Configured in `backend/app/core/config.py` (Pydantic Settings). Values marked **required** have no
default — the app fails fast at import if they're missing.

**Required**

| Variable | Notes |
| --- | --- |
| `APP_ENV` | one of `local`, `development`, `staging`, `production` |
| `DATABASE_URL` | must use `postgresql+asyncpg://` |
| `REDIS_URL` | e.g. `redis://localhost:6379/0` |
| `JWT_SECRET_KEY` | min 16 chars; use ≥32 random chars in real environments |

**Optional (defaults shown)**

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_PORT` | `8000` | |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | |
| `COOKIE_SECURE` | `true` | set `false` for local HTTP |
| `COOKIE_SAMESITE` | `lax` | `lax` \| `strict` \| `none` |
| `COOKIE_DOMAIN` | _(none)_ | |
| `RATE_LIMIT_PUBLIC_PER_MINUTE` | `100` | per IP |
| `RATE_LIMIT_AUTHENTICATED_PER_MINUTE` | `1000` | per user |
| `STRIPE_SECRET_KEY` | _(none)_ | prefer a restricted `rk_` key |
| `STRIPE_WEBHOOK_SECRET` | _(none)_ | `whsec_...` |
| `STRIPE_API_VERSION` | `2026-06-24.dahlia` | |
| `PAYMENT_CURRENCY` | `usd` | |
| `FRONTEND_BASE_URL` | `http://localhost:3000` | Stripe success/cancel redirect base |

Under Docker Compose, `DATABASE_URL` and `REDIS_URL` are composed internally from
`POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` and the `db` / `redis` service names — set those
(plus `JWT_SECRET_KEY` and any Stripe keys) in the root `.env` instead.

> Treat `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and `JWT_SECRET_KEY` as secrets. Keep them in
> `.env` (git-ignored) or a secrets manager — never commit real values.

## Backend: database migrations

Schema is defined with SQLAlchemy models (`backend/app/models/`) and versioned with Alembic. There is
currently one revision (the initial schema). Note that the test suite builds the schema directly from
`Base.metadata`, so keep migrations in sync with the models by hand.

```bash
cd backend
uv run alembic upgrade head                                   # apply all migrations
uv run alembic revision --autogenerate -m "describe change"   # generate a new migration
uv run alembic downgrade -1                                   # roll back one migration
```

## Backend: tests

pytest + pytest-asyncio, with coverage via pytest-cov. The suite spins the app over an httpx
`AsyncClient` and expects **test** Postgres/Redis on non-default ports (Postgres `:5433`, Redis `:6380`)
so it never touches your dev data — `backend/tests/conftest.py` creates/drops the schema and resets
rows between tests.

```bash
cd backend
uv run pytest                          # run everything
uv run pytest --cov=app --cov-report=term-missing   # with coverage
uv run pytest tests/test_orders.py     # a single file
```

Coverage spans auth/RBAC, catalog, cart, orders, checkout + webhooks, reviews, merchant/admin
analytics, rate limiting, and schema validation.

## Backend: linting & formatting

```bash
cd backend
uv run ruff check .        # lint
uv run ruff format .       # format
```

## Backend: pre-commit

Hooks are configured at the repo root (`.pre-commit-config.yaml`) and run Ruff against `backend/` on
every commit. Install once from the repo root:

```bash
uv run --project backend pre-commit install
```

## Stack choice: Frontend

**Next.js (App Router) + React 19**, **TypeScript** in strict mode
(`noUncheckedIndexedAccess` on top of `strict`), styled with **Tailwind CSS v3**
using CSS-variable theming. Server state via **TanStack Query**, client state via
**Zustand**, forms via **React Hook Form + Zod**. **MSW** for API mocking and
**Storybook** (`@storybook/nextjs-vite`, with the a11y addon) for the component
library. Linted with ESLint (flat config) and formatted with Prettier.

### Deviation from the recommended stack

The PRD recommends **Next.js 14**; this project uses the **current stable Next.js
(16.x)**. Justification: Next 14 is several majors behind and no longer receives
security patches; the App Router API we depend on is stable across 14→16, so
staying current avoids shipping a knowingly outdated framework. All other frontend
choices match the PRD (TypeScript, Tailwind, React Query, Zustand, RHF + Zod).
Tailwind is pinned to **v3** (not the newer v4) for the widest ecosystem/Storybook
compatibility. Next.js 16 is a major release — see [`frontend/AGENTS.md`](frontend/AGENTS.md).

## Frontend: local development

Requires Node.js and npm. Run from `frontend/`:

```bash
cd frontend
cp .env.example .env.local     # then adjust values (see "Environment variables")
npm install
npm run dev                    # http://localhost:3000
```

The dev server talks to the backend at `NEXT_PUBLIC_API_BASE_URL`
(default `http://localhost:8000`) — start the backend (Docker or uvicorn) first.

Scripts: `dev`, `build`, `start`, `lint`, `typecheck`, `format`, `format:check`,
`storybook` (Storybook dev on `:6006`), `build-storybook`.

### Frontend environment variables

Defined in `frontend/.env.local` (git-ignored); `frontend/.env.example` is the
committed template. Both are `NEXT_PUBLIC_`-prefixed (exposed to the browser).

| Variable | Default | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Base URL of the backend API. |
| `NEXT_PUBLIC_API_MOCKING` | _(empty)_ | Set to `enabled` to intercept API calls with MSW. |

### Frontend structure & conventions

```
frontend/src/
  app/          App Router: layout, page, providers, globals.css (design tokens)
  components/    reusable component library (built in a later phase)
  lib/           query-client, utils (cn)
  stores/        Zustand stores (cart starter)
  mocks/         MSW handlers + browser worker + node server + conditional init
  stories/       Storybook example stories (replaced by real ones later)
```

- **Theming / dark mode** — colours are CSS custom properties (HSL triplets) in
  `src/app/globals.css`, mapped to semantic Tailwind tokens
  (`bg-background`, `text-primary`, …). Dark mode is class-based (`class="dark"`
  on `<html>`); Storybook has a matching **Theme** toolbar.
- **API mocking** — MSW is wired but **off by default**; normal dev uses the real
  backend. Enable with `NEXT_PUBLIC_API_MOCKING=enabled`. Handlers live in
  `src/mocks/handlers.ts` (currently a stub). Contract stays in sync with the
  backend by generating TS types from `backend/openapi.json` (planned).
- **Validation** — backend Pydantic and frontend Zod don't conflict: they
  validate at different boundaries (server trust boundary vs. client UX). The
  shared contract is the OpenAPI spec.

## Known limitations

- **Order tracking is mocked** — `GET /orders/{id}/tracking` returns fabricated carrier / ETA data;
  there's no real carrier integration.
- **Access tokens can't be revoked mid-life** — changing a user's role or deactivating them (via
  `/admin`) doesn't invalidate their existing access token; the change takes effect when the 15-minute
  access token expires. There's no per-user access-token blocklist.
- **Rate limiting is a coarse fixed window** — a per-minute Redis counter, not a sliding window /
  token bucket, so bursts at minute boundaries aren't smoothed.
- **Payments require Stripe to be configured** — without `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET`,
  orders are created but never advance past `pending` (no webhook to confirm them).
- **Coupons are modeled but not wired into checkout** — the `Coupon` entity exists; discount
  application at checkout is not implemented yet.
- **Frontend is foundation-only** — `frontend/` has the scaffold, tooling, and
  providers wired, but no real components, pages, or API integration yet.
- **`npm audit` reports transitive advisories** in Next.js's bundled `postcss`
  and `sharp` (not direct deps). Don't run `npm audit fix --force` — it only
  suggests downgrading to `next@9`. These clear via a future Next.js patch bump.
