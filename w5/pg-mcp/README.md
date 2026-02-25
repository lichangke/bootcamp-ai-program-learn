# pg-mcp

Read-only PostgreSQL MCP server that converts natural language to SQL, validates safety, and executes queries.

## Requirements

- Python 3.12+
- `uv` (recommended) or `pip`
- Optional for integration tests: Docker + Docker Compose

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
docker compose -f docker-compose.test.yml up -d
set PG_MCP_RUN_INTEGRATION=1
uv run python -m pytest -q tests/integration
```

To stop the test database:

```bash
docker compose -f docker-compose.test.yml down -v
```

## Docker image

```bash
docker build -t pg-mcp .
docker run --rm pg-mcp
```

## Claude Desktop example

See `claude_desktop_config.example.json`.
