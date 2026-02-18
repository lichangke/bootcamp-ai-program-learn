# Quickstart: MySQL Support Verification

**Feature**: `002-mysql-support`  
**Scope**: Validate MySQL metadata extraction, read-only query execution, and natural-language SQL generation.

## Prerequisites

- Backend dependencies installed in `w2/db_query/backend`
- Backend service running at `http://127.0.0.1:8000`
- A reachable MySQL database (local sample: `todo_db`)

Local connectivity check example:

```bash
mysql --login-path=todo_local -u root todo_db -e "SELECT * FROM todos;"
```

## End-to-End Verification (todo_db)

### 1. Save MySQL connection

```bash
curl -X PUT http://127.0.0.1:8000/api/v1/dbs/todo-mysql ^
  -H "Content-Type: application/json" ^
  -d "{\"url\":\"mysql://root:YOUR_PASSWORD@127.0.0.1:3306/todo_db\"}"
```

Expected: HTTP `200`, connection object returned, metadata fetched and cached.

### 2. Verify metadata exists

```bash
curl http://127.0.0.1:8000/api/v1/dbs/todo-mysql
```

Expected:
- `metadata.databaseName` is `todo_db`
- `metadata.tables` contains `todos`
- `metadata.tables[].columns` includes table column definitions

### 3. Run read-only SQL

```bash
curl -X POST http://127.0.0.1:8000/api/v1/dbs/todo-mysql/query ^
  -H "Content-Type: application/json" ^
  -d "{\"sql\":\"SELECT * FROM todos\"}"
```

Expected:
- SQL accepted as single `SELECT`
- Backend auto-adds `LIMIT 1000` when missing
- Response returns `columns`, `rows`, `rowCount`, and `query`

### 4. Validate write query rejection

```bash
curl -X POST http://127.0.0.1:8000/api/v1/dbs/todo-mysql/query ^
  -H "Content-Type: application/json" ^
  -d "{\"sql\":\"DELETE FROM todos\"}"
```

Expected: HTTP `400`, validation error saying only `SELECT` statements are allowed.

### 5. Generate SQL from natural language

```bash
curl -X POST http://127.0.0.1:8000/api/v1/dbs/todo-mysql/query/natural ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\":\"show latest 10 todos\"}"
```

Expected: `generatedSql` returned, passes validation, and can be executed through `/query`.

## Quality Check Log

Commands executed in `w2/db_query/backend`:

- `.venv/Scripts/python.exe -m mypy src`
- `.venv/Scripts/python.exe -m ruff check src tests`
- `.venv/Scripts/python.exe -m pytest`

Record:
- Date/time: `2026-02-18 18:36:57 +08:00`
- Command outputs:
  - `mypy`: `Success: no issues found in 19 source files` (exit `0`)
  - `ruff`: `All checks passed!` (exit `0`)
  - `pytest`: `collected 0 items` with cache warning (exit `5`)
- Pass/fail summary:
  - Static quality gates (`mypy`, `ruff`) passed.
  - Test run has no collected tests in current backend workspace.
