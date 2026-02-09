# Quick Start: 数据库查询工具

**Feature**: 002-db-query-tool
**Date**: 2026-02-09
**Purpose**: Development setup and usage guide

## Prerequisites

### Required Software

- **Python 3.11+**: Backend runtime
- **Node.js 18+**: Frontend runtime
- **uv**: Python package manager (`pip install uv`)
- **PostgreSQL**: Target database for queries (local or remote)

### Environment Setup

1. **OpenAI API Key**: Required for natural language SQL generation
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

2. **Storage Directory**: Will be created automatically at `~/.db_query/`

## Installation

### Backend Setup

```bash
# Navigate to backend directory
cd w2/db_query/backend

# Create virtual environment and install dependencies with uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Install development dependencies
uv pip install pytest pytest-cov mypy black ruff
```

### Frontend Setup

```bash
# Navigate to frontend directory
cd w2/db_query/frontend

# Install dependencies
npm install

# Or with yarn
yarn install
```

## Development

### Running the Backend

```bash
cd w2/db_query/backend

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Run development server with auto-reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Backend will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Running the Frontend

```bash
cd w2/db_query/frontend

# Start development server
npm run dev

# Or with yarn
yarn dev

# Frontend will be available at http://localhost:5173
```

### Running Both (Recommended)

Use two terminal windows:

**Terminal 1 (Backend)**:
```bash
cd w2/db_query/backend
source .venv/bin/activate
uvicorn src.main:app --reload
```

**Terminal 2 (Frontend)**:
```bash
cd w2/db_query/frontend
npm run dev
```

## Usage

### 1. Add a Database Connection

**Via UI**:
1. Open http://localhost:5173
2. Click "Add Database"
3. Enter connection name (e.g., "local-postgres")
4. Enter PostgreSQL URL: `postgres://user:password@localhost:5432/dbname`
5. Click "Save" - system will validate connection and fetch metadata

**Via API**:
```bash
curl -X PUT http://localhost:8000/api/v1/dbs/local-postgres \
  -H "Content-Type: application/json" \
  -d '{"url": "postgres://postgres:postgres@localhost:5432/postgres"}'
```

### 2. Browse Database Schema

**Via UI**:
1. Click on a saved connection
2. View list of tables and views
3. Expand tables to see columns, types, and constraints

**Via API**:
```bash
curl http://localhost:8000/api/v1/dbs/local-postgres
```

### 3. Execute SQL Query

**Via UI**:
1. Select a database connection
2. Enter SQL in the Monaco editor:
   ```sql
   SELECT * FROM users WHERE active = true
   ```
3. Click "Execute"
4. View results in table format

**Via API**:
```bash
curl -X POST http://localhost:8000/api/v1/dbs/local-postgres/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM users LIMIT 10"}'
```

### 4. Generate SQL from Natural Language

**Via UI**:
1. Select a database connection
2. Switch to "Natural Language" tab
3. Enter question: "Show me all active users created in the last 30 days"
4. Click "Generate SQL"
5. Review generated SQL
6. Click "Execute" to run the query

**Via API**:
```bash
# Generate SQL
curl -X POST http://localhost:8000/api/v1/dbs/local-postgres/query/natural \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Show me all active users"}'

# Then execute the generated SQL
curl -X POST http://localhost:8000/api/v1/dbs/local-postgres/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "<generated-sql>"}'
```

## Testing

### Backend Tests

```bash
cd w2/db_query/backend

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test types
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests only
pytest tests/contract/      # Contract tests only

# Type checking
mypy src/

# Linting
ruff check src/
black --check src/
```

### Frontend Tests

```bash
cd w2/db_query/frontend

# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Type checking
npm run type-check

# Linting
npm run lint
```

## Configuration

### Backend Configuration

Configuration via environment variables:

```bash
# Required
export OPENAI_API_KEY="sk-..."

# Optional (with defaults)
export DB_QUERY_STORAGE_PATH="~/.db_query/db_query.db"  # SQLite storage location
export DB_QUERY_DEFAULT_LIMIT=1000                       # Default query row limit
export DB_QUERY_QUERY_TIMEOUT=30                         # Query timeout in seconds
export DB_QUERY_CORS_ORIGINS="*"                         # CORS allowed origins
```

### Frontend Configuration

Edit `frontend/.env`:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## Project Structure

```
w2/db_query/
├── backend/
│   ├── src/
│   │   ├── models/          # Pydantic models
│   │   ├── services/        # Business logic
│   │   ├── api/             # FastAPI routes
│   │   ├── storage/         # SQLite persistence
│   │   └── main.py          # App entry point
│   ├── tests/
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/           # Refine pages
│   │   ├── services/        # API client
│   │   └── types/           # TypeScript types
│   ├── tests/
│   └── package.json
│
└── README.md
```

## Common Issues

### Backend Issues

**Issue**: `ModuleNotFoundError: No module named 'src'`
**Solution**: Make sure you're in the backend directory and virtual environment is activated

**Issue**: `sqlglot.errors.ParseError`
**Solution**: Check SQL syntax - only SELECT statements allowed, no multi-statement queries

**Issue**: `openai.error.AuthenticationError`
**Solution**: Verify `OPENAI_API_KEY` environment variable is set correctly

**Issue**: `psycopg2.OperationalError: could not connect`
**Solution**: Verify PostgreSQL connection URL is correct and database is accessible

### Frontend Issues

**Issue**: `CORS error when calling API`
**Solution**: Ensure backend is running and CORS is configured to allow frontend origin

**Issue**: `Monaco Editor not loading`
**Solution**: Check that `@monaco-editor/react` is installed correctly

**Issue**: `Type errors in TypeScript`
**Solution**: Run `npm run type-check` to see detailed errors, ensure types match API contracts

## API Documentation

Interactive API documentation available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Data Storage

### SQLite Database Location

- **Path**: `~/.db_query/db_query.db`
- **Contents**: Database connections and cached metadata
- **Backup**: Copy the file to backup all connections

### Viewing SQLite Data

```bash
# Open SQLite CLI
sqlite3 ~/.db_query/db_query.db

# List tables
.tables

# View connections
SELECT * FROM connections;

# View metadata
SELECT connection_name, table_name, table_type FROM metadata;
```

## Security Notes

⚠️ **Important Security Considerations**:

1. **No Authentication**: This tool has no authentication by design (constitution requirement)
2. **Trusted Environment Only**: Only use in trusted/local environments
3. **Database Credentials**: Connection URLs with passwords are stored in SQLite
4. **CORS Open**: Backend accepts requests from any origin
5. **Read-Only**: SQL execution is restricted to SELECT statements only

## Performance Tips

1. **Metadata Caching**: Schema metadata is cached in SQLite - refresh only when schema changes
2. **Query Limits**: Always include LIMIT clause for large tables (default 1000 applied automatically)
3. **Connection Pooling**: Backend reuses database connections for better performance
4. **Natural Language**: LLM calls take 1-3 seconds - use SQL directly for faster queries

## Next Steps

1. **Add Your First Connection**: Follow "Add a Database Connection" above
2. **Explore Schema**: Browse tables and columns
3. **Run Queries**: Try SQL queries and natural language generation
4. **Review Tests**: Check `tests/` directories for examples
5. **Read API Docs**: Visit http://localhost:8000/docs for full API reference

## Troubleshooting

For issues not covered here:
1. Check backend logs in terminal
2. Check browser console for frontend errors
3. Verify environment variables are set
4. Ensure PostgreSQL database is accessible
5. Review [data-model.md](./data-model.md) for entity definitions
6. Review [contracts/openapi.yaml](./contracts/openapi.yaml) for API contracts

## Development Workflow

1. **Make Changes**: Edit code in `src/` directories
2. **Run Tests**: `pytest` (backend) or `npm test` (frontend)
3. **Type Check**: `mypy src/` (backend) or `npm run type-check` (frontend)
4. **Lint**: `ruff check src/` (backend) or `npm run lint` (frontend)
5. **Test Manually**: Use UI or API to verify changes
6. **Commit**: Follow constitution guidelines for commits

## Constitution Compliance Checklist

When developing, ensure:
- ✅ All Python code has type annotations (mypy passes)
- ✅ All TypeScript code has type annotations (tsc passes)
- ✅ All JSON responses use camelCase
- ✅ No authentication code added
- ✅ SQL validation enforces SELECT-only
- ✅ CORS allows all origins
- ✅ Storage uses `~/.db_query/db_query.db`
- ✅ OpenAI key from environment variable only
- ✅ Tests written before implementation (TDD)
