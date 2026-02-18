# Project Alpha Backend

## Run

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

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
