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

### MCP stdio (default)

```bash
uv run python -m pg_mcp
```

The server reads runtime configuration from `.env` or nested env vars (see `.env.example`).

### MCP Streamable HTTP

Set the transport-related env vars, then run the same entrypoint:

```bash
export SERVER__TRANSPORT=streamable-http
export SERVER__HOST=127.0.0.1
export SERVER__PORT=8000
export SERVER__PATH=/mcp
export SERVER__STATELESS_HTTP=false
uv run python -m pg_mcp
```

FastMCP will expose the MCP endpoint at `http://<host>:<port><path>`.
For example: `http://127.0.0.1:8000/mcp`.

For MCP clients with strict startup handshake limits, keep
`SCHEMA_CACHE__PRELOAD_ON_STARTUP=false` (default). Schema is lazily discovered
on first query per database.

The server now supports:

- JSON structured logs with end-to-end `request_id`
- bounded DB pool init retries with degraded startup for partially unhealthy DBs
- optional in-process query rate limiting (`QUERY__MAX_CONCURRENT_REQUESTS`, `QUERY__RATE_LIMIT_PER_MINUTE`)
- configurable transports: `stdio` (default) and `streamable-http` (also supports `http`/`sse` via `SERVER__TRANSPORT`)

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
