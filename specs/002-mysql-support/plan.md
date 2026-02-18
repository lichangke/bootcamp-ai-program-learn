# Implementation Plan: MySQL Support for DB Query Tool

**Branch**: `002-mysql-support` | **Date**: 2026-02-18 | **Reference**: `specs/002-db-query-tool/plan.md`

## Summary

Extend the existing PostgreSQL-first DB query tool to support MySQL for:

1. Connection validation and metadata extraction
2. Read-only SQL validation/execution
3. Natural-language SQL generation and fallback logic

The implementation keeps existing API routes and UI flows while adding dialect-aware behavior.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.0+ (frontend)  
**Primary Dependencies**:
- Backend: FastAPI, Pydantic, sqlglot, psycopg2, pymysql, OpenAI SDK, SQLite
- Frontend: React, TypeScript, Ant Design, Monaco Editor
**Storage**: SQLite at `~/.db_query/db_query.db` for saved connections and metadata cache  
**Project Type**: Web application (`w2/db_query/backend` + `w2/db_query/frontend`)  
**Constraints**:
- Keep read-only SQL guardrails (`SELECT` only, single statement, default `LIMIT 1000`)
- Keep camelCase JSON API responses
- No authentication/authorization
- Backward-compatible PostgreSQL support while adding MySQL

## Project Structure

```text
w2/db_query/
├── backend/
│   ├── src/
│   │   ├── api/v1/
│   │   ├── models/
│   │   ├── services/
│   │   └── storage/
│   └── pyproject.toml
├── frontend/
│   └── src/
└── README.md
```

## Implementation Strategy

1. Add dialect detection and connector factory in backend services.
2. Introduce MySQL metadata query paths in metadata service.
3. Make SQL parser/validator dialect-aware in query service and API routing.
4. Make natural-language SQL generation dialect-aware.
5. Update frontend labels/help text and supporting docs/contracts.
