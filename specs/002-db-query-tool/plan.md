# Implementation Plan: 数据库查询工具

**Branch**: `002-db-query-tool` | **Date**: 2026-02-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-db-query-tool/spec.md`

## Summary

A database query tool that allows users to connect to PostgreSQL databases, browse schema metadata, execute read-only SQL queries, and generate SQL from natural language descriptions. The tool consists of a Python/FastAPI backend with a React/Refine frontend, storing connection metadata locally in SQLite.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.0+ (frontend)
**Primary Dependencies**:
- Backend: FastAPI, Pydantic, sqlglot, OpenAI SDK, psycopg2, SQLite
- Frontend: React 19+, Refine 5, Ant Design, TailwindCSS, Monaco Editor
**Storage**: SQLite at `~/.db_query/db_query.db` for connection metadata; PostgreSQL as query target
**Testing**: pytest (backend), Vitest/React Testing Library (frontend)
**Target Platform**: Local development environment (Windows/macOS/Linux)
**Project Type**: Web application (backend + frontend)
**Performance Goals**:
- Query execution: <5 seconds for 95% of queries
- Metadata fetch: <10 seconds for typical database
- Natural language generation: <3 seconds
**Constraints**:
- Read-only SQL execution (SELECT only)
- Default LIMIT 1000 on queries
- No authentication/authorization
- CORS allows all origins
**Scale/Scope**:
- Single user tool
- Support multiple saved database connections
- Handle databases with up to 1000 tables/views

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verify compliance with `.specify/memory/constitution.md`:

- [x] **Type Safety**: Backend uses Ergonomic Python with strict types (Pydantic models), Frontend uses TypeScript with strict types
- [x] **JSON Convention**: All backend JSON uses camelCase (FastAPI with Pydantic alias_generator)
- [x] **No Authentication**: No auth/authorization code (intentional constraint)
- [x] **Read-Only SQL**: Only SELECT allowed (sqlglot parser validation), multi-statement rejected, default LIMIT 1000
- [x] **CORS Permissive**: Backend allows all origins (FastAPI CORS middleware)
- [x] **Local State**: Uses `~/.db_query/db_query.db` for persistence (SQLite)
- [x] **API Key Security**: OpenAI key from `OPENAI_API_KEY` env var, never persisted
- [x] **Code Quality**: Type checking passes (mypy for Python, tsc for TypeScript), all code has type annotations
- [x] **Error Handling**: JSON errors with camelCase, human-readable messages (FastAPI exception handlers)
- [x] **Testing**: Contract tests for APIs, integration tests for journeys, TDD approach

**Constitution Compliance**: ✅ All principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/002-db-query-tool/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── openapi.yaml
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
w2/db_query/
├── backend/
│   ├── src/
│   │   ├── models/          # Pydantic models (camelCase aliases)
│   │   │   ├── connection.py
│   │   │   ├── metadata.py
│   │   │   ├── query.py
│   │   │   └── error.py
│   │   ├── services/        # Business logic
│   │   │   ├── connection_service.py
│   │   │   ├── metadata_service.py
│   │   │   ├── query_service.py
│   │   │   └── llm_service.py
│   │   ├── api/             # FastAPI routes
│   │   │   ├── v1/
│   │   │   │   ├── dbs.py
│   │   │   │   └── query.py
│   │   │   └── middleware.py
│   │   ├── storage/         # SQLite persistence
│   │   │   └── sqlite_store.py
│   │   └── main.py          # FastAPI app entry
│   ├── tests/
│   │   ├── contract/        # API contract tests
│   │   ├── integration/     # End-to-end tests
│   │   └── unit/            # Unit tests
│   ├── pyproject.toml       # uv project config
│   └── README.md
│
├── frontend/
│   ├── src/
│   │   ├── components/      # Reusable UI components
│   │   │   ├── DatabaseList.tsx
│   │   │   ├── SchemaViewer.tsx
│   │   │   ├── SqlEditor.tsx
│   │   │   ├── QueryResults.tsx
│   │   │   └── NaturalLanguageInput.tsx
│   │   ├── pages/           # Refine pages/resources
│   │   │   ├── databases/
│   │   │   │   ├── list.tsx
│   │   │   │   ├── create.tsx
│   │   │   │   └── show.tsx
│   │   │   └── query/
│   │   │       └── index.tsx
│   │   ├── services/        # API client
│   │   │   └── api.ts
│   │   ├── types/           # TypeScript types
│   │   │   └── models.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── tests/
│   │   ├── integration/
│   │   └── unit/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── README.md
│
└── README.md                # Project overview
```

**Structure Decision**: Web application structure (Option 2) selected because the feature requires both a backend API (FastAPI) and a frontend UI (React). The backend handles database connections, SQL parsing, and LLM integration, while the frontend provides the user interface for browsing schemas and executing queries.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations - all constitution principles are satisfied by the chosen architecture.

## Phase 0: Research

See [research.md](./research.md) for detailed research findings on:
- SQL parsing with sqlglot
- PostgreSQL metadata extraction
- OpenAI SDK integration for natural language SQL generation
- FastAPI best practices for camelCase JSON serialization
- Monaco Editor integration in React
- Refine 5 patterns for CRUD operations

## Phase 1: Design

### Data Model

See [data-model.md](./data-model.md) for complete entity definitions.

### API Contracts

See [contracts/openapi.yaml](./contracts/openapi.yaml) for full OpenAPI specification.

### Quick Start

See [quickstart.md](./quickstart.md) for development setup and usage instructions.

## Phase 2: Task Generation

Tasks will be generated via `/speckit.tasks` command after Phase 1 completion.
