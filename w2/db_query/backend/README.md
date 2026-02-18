# DB Query Backend

FastAPI backend for the DB Query Tool.

## Stack

- Python 3.12+
- FastAPI + Pydantic
- Database drivers: `psycopg2` (PostgreSQL), `pymysql` (MySQL)
- SQL parser: `sqlglot`
- Local persistence: SQLite (`~/.db_query/db_query.db`)

## Run Locally

```bash
cd w2/db_query/backend
uv sync --no-install-project
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

## Quality Checks

```bash
cd w2/db_query/backend
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pytest
```

## API Endpoints

- `GET /health`
- `GET /health/llm`
- `GET /api/v1/dbs`
- `PUT /api/v1/dbs/{name}`
- `GET /api/v1/dbs/{name}`
- `POST /api/v1/dbs/{name}/refresh`
- `DELETE /api/v1/dbs/{name}`
- `POST /api/v1/dbs/{name}/query`
- `POST /api/v1/dbs/{name}/query/natural`

## Environment Variables

- `DEEPSEEK_API_KEY` (recommended for natural language SQL generation)
- `DEEPSEEK_BASE_URL` (optional, default: `https://api.deepseek.com`)
- `OPENAI_API_KEY` (backward-compatible fallback key name)

## Notes

- SQL execution is strictly read-only (`SELECT` only, single statement, auto `LIMIT 1000`).
- Backend JSON responses use camelCase fields.
- Authentication/authorization is intentionally out of scope for this project.

## Connection URL Examples

- PostgreSQL: `postgres://user:pass@host:5432/db_name`
- MySQL: `mysql://user:pass@host:3306/db_name`

For local verification with an existing MySQL login-path:

```bash
mysql --login-path=todo_local -u root todo_db -e "SELECT * FROM todos;"
```
