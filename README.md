# ABASE Manager v2 — FastAPI + Next.js 15

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009485)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-19-087ea4)](https://react.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-4.0-06B6D4)](https://tailwindcss.com/)

Monorepo pnpm/Turborepo that powers the next generation of **ABASE Manager**, featuring a FastAPI backend with SQLAlchemy/Alembic, a Next.js 15 App Router frontend, realtime updates via SSE + WebSockets, and a shared UI library based on HeroUI + Tailwind 4.

---

## ✨ Highlights

- **FastAPI 0.111** backend with async SQLAlchemy 2, PostgreSQL 16, Redis 7, Alembic migrations and seed scripts.
- **OIDC + JWT** authentication workflow with refresh tokens, RBAC, session caching in Redis and revocation support.
- **Realtime stack**: Server-Sent Events (notifications) & WebSockets (updates) orchestrated through Redis pub/sub.
- **Next.js 15 + React 19** frontend (App Router) with modular hooks (`useSSE*`, `useRealtimeUpdates`) and an updated AuthContext.
- **Shared UI** with Tailwind CSS 4 + HeroUI components documented in Storybook 8.1.
- **Business modules**: Complete analysis and treasury management interfaces with real-time updates.
- **Developer experience**: pnpm workspaces, Turborepo pipelines, linting, formatting, and dockerised local stack.

---

## 🧱 Repository Structure

```
abasev2/
├── apps/
│   ├── api/                # FastAPI application
│   │   ├── app/            # Application source (routers, services, models, auth, events)
│   │   ├── migrations/     # Alembic environment and versions
│   │   ├── alembic.ini
│   │   └── pyproject.toml
│   └── web/                # Next.js 15 frontend
│       └── src/
│           ├── app/        # App Router routes
│           ├── components/
│           ├── contexts/   # AuthProvider, realtime hooks
│           ├── hooks/
│           └── lib/
├── packages/
│   └── ui/                 # @abase/ui design system
├── scripts/
│   ├── init_db.sh          # Runs Alembic + seeds (used by Docker entrypoint)
│   └── seed_users.py       # Creates default users & roles
├── docker/                 # Dockerfiles for api & web
├── docker-compose.yml      # Services: postgres, redis, api, web
├── docker-compose.dev.yml  # Overrides for local dev (hot reload)
├── turbo.json              # Turborepo pipelines
└── pnpm-workspace.yaml
```

---

## ⚙️ Prerequisites

- **Node.js 20+** and **pnpm 8.15+**
- **Python 3.11** with `venv`
- **Docker + Docker Compose** (for infrastructure and/or full stack)
- **Redis 7** and **PostgreSQL 16** (managed automatically via Docker)

---

## 🚀 Quickstart (Docker)

```bash
# 1. Install workspace dependencies
pnpm install

# 2. Build and run the full stack
docker-compose up --build

# 3. Access the services
# API (FastAPI docs):      http://localhost:8000/docs
# Next.js frontend:        http://localhost:3000
# Storybook (optional):    pnpm storybook
```

The API container entrypoint executes `scripts/init_db.sh`, which automatically applies Alembic migrations and seeds the default users (`admin@abase.local`, `analista@abase.local`, `tesouraria@abase.local`, `agente@abase.local`).

> 📋 **Detailed Setup Instructions**: See `COMANDOS_EXECUCAO.md` for comprehensive setup, troubleshooting, and execution commands for Windows environments.

---

## 🛠️ Local Development (API)

```bash
# 1. Install backend dependencies
cd apps/api
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

# 2. Provision the database & redis (Docker recommended)
docker-compose up -d postgres redis

# 3. Run migrations & seeds
alembic upgrade head
python ../../scripts/seed_users.py

# 4. Start FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Key directories in `apps/api/app`:

- `auth/` — strategies (OIDC, local, JWT), manager (Singleton), factories (token/session), permissions and RBAC.
- `models/` — SQLAlchemy models (Users, Associados, Cadastros, EventLogs).
- `schemas/` — Pydantic models for request/response DTOs.
- `routers/` — Domain routes (`auth`, `cadastros`, `analise`, `tesouraria`, `relatorios`, `health`).
- `events/` — SSE app + Redis-backed broadcast loop, WebSocket connection manager.
- `dependencies/` — FastAPI dependencies (db session, redis, auth guards).

---

## 🖥️ Local Development (Web)

```bash
# 1. Install root dependencies (once)
pnpm install

# 2. Start the Next.js app
dcd apps/web
pnpm dev

# 3. Environment (apps/web/.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_OIDC_ISSUER=<your-oidc-issuer>
NEXT_PUBLIC_OIDC_CLIENT_ID=<client-id>
```

Key frontend updates:

- `contexts/AuthContext.tsx` implements the new `/api/v1/auth` flow (local + OIDC), refresh handling, and exposes `handleOIDCCallback` for the callback page.
- `lib/api-client.ts` stores both access/refresh tokens, exposes `getRefreshToken`, and transparently retries requests on 401.
- `hooks/useSSEEvents.ts` and `hooks/useRealtimeUpdates.ts` connect to the new SSE (`/api/v1/sse`) and WebSocket (`/api/v1/ws/updates`) endpoints, with auto-reconnect strategies and toast integration.

---

## 🔐 Authentication & RBAC

- **Local login** calls `POST /api/v1/auth/login` with `provider: "local"` (email/password).
- **OIDC login** exchanges the authorization code via `/api/v1/auth/login` (`provider: "oidc"` + PKCE metadata).
- **Refresh tokens** via `POST /api/v1/auth/refresh` (JWT strategy in Redis).
- **Logout** via `POST /api/v1/auth/logout` (revokes access token and clears session cache).
- **RBAC** maps roles (`ADMIN`, `ANALISTA`, `TESOURARIA`, `AGENTE`) to granular permissions.

Authentication state lives in Redis (`session:{user_id}`, `refresh:{token}`, `blacklist:{jti}`), allowing clustered deployments.

---

## 🔄 Realtime Events

- **SSE** (`/api/v1/sse`) broadcasts domain events (cadastro lifecycle, payments, contracts) using `fastapi-sse` and Redis pub/sub.
- **WebSockets** (`/api/v1/ws/updates`) push lightweight update messages to connected clients.
- Frontend hooks (`useSSEEvents`, `useRealtimeUpdates`) centralise reconnection, notification rendering, and state refresh.

To publish from the backend:

```python
from app.events import publish_event

await publish_event(
    channel="cadastros",
    data={"type": "CADASTRO_APROVADO", "payload": cadastro_id},
    event="cadastro.aprovado",
)
```

---

## 📘 Storybook

Storybook is configured inside the workspace `storybook/` package and consumes the shared `@abase/ui` library as well as Tailwind 4 tokens.

```bash
# Development
yarn storybook dev --config-dir storybook
# or
pnpm --filter @abase/storybook dev

# Static build
pnpm --filter @abase/storybook build
```

Dependencies upgraded to Storybook **8.1.x** for React 19 compatibility.

---

## 🧪 Testing & Tooling

| Area          | Command / Tool                         |
|---------------|-----------------------------------------|
| FastAPI tests | `cd apps/api && pytest` (coming soon)   |
| Lint backend  | `ruff check apps/api/app`               |
| Type check    | `pyright apps/api/app` (planned)        |
| Frontend lint | `pnpm lint` (workspace)                 |
| Storybook     | `pnpm storybook dev`                    |

---

## 👥 Seed Users

After running `scripts/seed_users.py`, the following accounts are created (passwords can be changed in `.env`):

| Role        | Email                     | Password        |
|-------------|---------------------------|-----------------|
| ADMIN       | `admin@abase.local`       | `admin123`      |
| ANALISTA    | `analista@abase.local`    | `analista123`   |
| TESOURARIA  | `tesouraria@abase.local`  | `tesouraria123` |
| AGENTE      | `agente@abase.local`      | `agente123`     |

---

## 🎯 Current Features

### Business Modules
- **Analysis Module** (`/analise`): Complete interface for analyzing member registrations with real-time status updates, filtering, and detailed views.
- **Treasury Module** (`/tesouraria`): Financial management interface with payment tracking, document management, and status monitoring.
- **Real-time Updates**: SSE integration for live notifications and status changes across all modules.

### UI Components (Storybook)
- **Button**: All variants, colors, sizes, and icon combinations
- **StatusBadge**: Business and generic status indicators
- **DataTable**: Advanced tables with filtering, pagination, and actions
- **Timeline**: Event tracking and status timelines
- **FileUpload**: Document upload with progress and validation
- **FilterBuilder**: Advanced filtering capabilities
- **FormField**: Complete form field components
- **MultiStepForm**: Multi-step form workflows
- **DocumentPreview**: PDF and image preview functionality
- **DesignTokens**: Complete design system documentation

## 🗺️ Roadmap (Stage 2)

- Expand Alembic migrations and SQLAlchemy models for the full business schema.
- Implement document upload and management workflows.
- Add comprehensive audit logging and activity tracking.
- Improve automated test coverage (backend + frontend e2e).
- Finalise localisation and accessibility for the React UI/Storybook.
- Add advanced reporting and analytics features.

---

## 📄 License

This project is distributed under the MIT License. See `LICENSE` for more information.
