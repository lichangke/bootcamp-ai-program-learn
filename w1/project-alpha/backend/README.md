# Project Alpha Backend

## Run

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

The backend settings load `.env` from project root (`../.env`) first.

## Migrations

```bash
alembic -c alembic.ini upgrade head
alembic -c alembic.ini downgrade -1
```

The first migration creates:

- `tickets`
- `tags` with case-insensitive unique index `uk_tags_name_ci`
- `ticket_tags`

## Health Check

```bash
curl http://localhost:8000/api/health
```

The health endpoint validates application availability and PostgreSQL connectivity.

## Ticket API

```text
GET    /api/tickets
POST   /api/tickets
GET    /api/tickets/{ticket_id}
PUT    /api/tickets/{ticket_id}
DELETE /api/tickets/{ticket_id}
PATCH  /api/tickets/{ticket_id}/complete
PATCH  /api/tickets/{ticket_id}/reopen
```

Ticket list query example:

```text
GET /api/tickets?tag_id=1&q=deploy&status=open&page=1&page_size=20
```

## Tag API

```text
GET    /api/tags
POST   /api/tags
PUT    /api/tags/{tag_id}
DELETE /api/tags/{tag_id}
```

## Dev Commands

```bash
ruff check .
ruff format .
pytest
```

Run performance test:

```bash
pytest -q tests/test_ticket_list_performance.py
```

## Seed Data

From `./w1/project-alpha`:

```bash
make backend-db-seed
```

This loads `seed.sql` into `DATABASE_URL` and inserts:

- 50 tags
- 50 tickets
- 150 ticket-tag links
