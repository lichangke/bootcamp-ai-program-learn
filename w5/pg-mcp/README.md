# pg-mcp

Read-only PostgreSQL MCP server that converts natural language to SQL, validates safety, and executes queries.

## Requirements

- Python 3.12+
- `uv` (recommended) or `pip`
- Optional for integration tests: local PostgreSQL instance

## Local setup

```bash
uv sync --dev
uv run ruff check .
uv run python -m pytest -q
```

## Run server

```bash
uv run python -m pg_mcp
```

The server reads runtime configuration from `.env` or nested env vars (see `.env.example`).

For MCP clients with strict startup handshake limits, keep
`SCHEMA_CACHE__PRELOAD_ON_STARTUP=false` (default). Schema is lazily discovered
on first query per database.

## Integration tests (P9)

```bash
# 1) prepare test database and schema data
#    psql -h 127.0.0.1 -p 5433 -U test_user -d test_db -f tests/fixtures/init.sql

# 2) run integration tests
set PG_MCP_RUN_INTEGRATION=1
uv run python -m pytest -q tests/integration
```

## Claude Desktop example

See `claude_desktop_config.example.json`.

## Codex usage guide

See `docs/CODEX_USAGE.md` for full setup, MCP registration, and headless verification steps.
