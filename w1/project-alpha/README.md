# Project Alpha (Day 1-4)

This directory contains the Day 1 to Day 4 implementation for Project Alpha.

## Structure

```text
./w1/project-alpha/
  backend/   # FastAPI backend skeleton
  frontend/  # Vite + React + Tailwind + shadcn/ui skeleton
  tests/     # Cross-layer test assets
  docs/      # Progress notes and docs
```

## Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 15+ (local)

## Quick Start

1. Create env file:

```bash
cp .env.example .env
```

2. Start backend:

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

3. Start frontend:

```bash
cd frontend
npm install
npm run dev
```

4. Verify health endpoint:

```bash
curl http://localhost:8000/api/health
```

5. Run DB migration:

```bash
cd backend
alembic -c alembic.ini upgrade head
```

## Unified Commands

From `./w1/project-alpha`:

```bash
make lint
make format
make test
make backend-db-upgrade
```

## Day 1 Delivered

- FastAPI layered skeleton with `GET /api/health`
- PostgreSQL connectivity probe in health check
- Vite + TypeScript + Tailwind + shadcn/ui placeholder frontend
- `.env.example`, README, lint/format/test baseline commands

## Day 2 Delivered

- Alembic migration toolchain and first migration
- Core tables: `tickets`, `tags`, `ticket_tags`
- DB constraints for `status` and `completed_at`
- Case-insensitive unique index on `LOWER(tags.name)`
- Repository CRUD skeleton for tickets/tags/ticket_tags
- Repository test scaffold for migration and CRUD validation

## Day 3 Delivered

- Ticket API endpoints:
  - `POST /api/tickets`
  - `GET /api/tickets/{ticket_id}`
  - `PUT /api/tickets/{ticket_id}`
  - `DELETE /api/tickets/{ticket_id}`
  - `PATCH /api/tickets/{ticket_id}/complete`
  - `PATCH /api/tickets/{ticket_id}/reopen`
- Service-layer business rules:
  - title length validation (`1..200` after trim)
  - complete/reopen updates `status` and `completed_at`
  - update/create tag handling uses full replacement strategy
- Ticket API and service tests added and passing

## Day 4 Delivered

- Tag API endpoints:
  - `GET /api/tags`
  - `POST /api/tags`
  - `PUT /api/tags/{tag_id}`
  - `DELETE /api/tags/{tag_id}`
- Ticket list endpoint with filters and pagination:
  - `GET /api/tickets?tag_id=&q=&status=&page=&page_size=`
  - supports `tag_id`, title fuzzy search `q`, `status=open|done`, and pagination
  - enforces `page_size <= 100`
- Tag deletion keeps relation consistency via DB transaction + `ON DELETE CASCADE`
- Added tests for tag API/service and ticket list filtering/pagination behavior
