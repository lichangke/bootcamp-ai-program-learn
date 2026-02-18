# Project Alpha (Day 1-8)

Project Alpha is a ticket management tool with tag-based organization.
This folder contains the full Day 1 to Day 8 implementation from
`specs/w1/002-implementation-plan.md`.

## Structure

```text
./w1/project-alpha/
  backend/   # FastAPI backend
  frontend/  # Vite + React + Tailwind frontend
  tests/     # cross-layer assets (reserved)
  docs/      # progress logs, API rest samples, acceptance docs
  seed.sql   # repeatable seed data (50 tickets / 50 tags)
```

## Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 15+ (local)
- `make`

## Quick Start

From `./w1/project-alpha`:

```bash
cp .env.example .env
make backend-install
make frontend-install
make backend-db-upgrade
make backend-db-seed
```

Start services in two terminals:

```bash
make backend-dev
```

```bash
make frontend-dev
```

Verify:

- Backend health: `http://localhost:8000/api/health`
- Frontend UI: `http://localhost:5173`

## Make Commands

From `./w1/project-alpha`:

```bash
make backend-install
make backend-lint
make backend-format
make backend-test
make backend-test-performance
make backend-db-upgrade
make backend-db-downgrade
make backend-db-seed
make backend-dev

make frontend-install
make frontend-lint
make frontend-format
make frontend-build
make frontend-test
make frontend-e2e
make frontend-dev

make lint
make format
make test
```

## API Coverage

Implemented and documented in `docs/test.rest`:

- Health: `GET /api/health`
- Ticket CRUD + state transition:
  - `GET /api/tickets`
  - `POST /api/tickets`
  - `GET /api/tickets/{ticket_id}`
  - `PUT /api/tickets/{ticket_id}`
  - `DELETE /api/tickets/{ticket_id}`
  - `PATCH /api/tickets/{ticket_id}/complete`
  - `PATCH /api/tickets/{ticket_id}/reopen`
- Tag CRUD:
  - `GET /api/tags`
  - `POST /api/tags`
  - `PUT /api/tags/{tag_id}`
  - `DELETE /api/tags/{tag_id}`

## Day 5-8 Notes

- Day 5/6: frontend main flow, debounce/filter UX, loading/error/empty states,
  confirm + toast feedback, optimistic rollback.
- Day 7: backend integration tests, frontend component tests, Playwright smoke,
  performance test for ticket list at 10k scale.
- Day 8: acceptance review and documentation freeze:
  see `docs/final-acceptance.md` and `docs/open-items.md`.
