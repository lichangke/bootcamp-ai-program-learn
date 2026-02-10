# Tasks: 数据库查询工具

**Input**: Design documents from `/specs/002-db-query-tool/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/openapi.yaml

**Organization**: Tasks organized into 3 phases for efficient implementation

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `w2/db_query/backend/src/`
- **Frontend**: `w2/db_query/frontend/src/`
- **Tests**: `w2/db_query/backend/tests/` and `w2/db_query/frontend/tests/`

---

## Phase 1: Setup & Foundation

**Purpose**: Project initialization and shared infrastructure that blocks all user stories

### Backend Setup

- [X] T001 Create backend project structure at w2/db_query/backend/
- [X] T002 Initialize Python project with uv in w2/db_query/backend/pyproject.toml
- [X] T003 [P] Configure mypy for type checking in w2/db_query/backend/pyproject.toml
- [X] T004 [P] Configure ruff for linting in w2/db_query/backend/pyproject.toml
- [X] T005 [P] Create base CamelCaseModel with Pydantic alias_generator in w2/db_query/backend/src/models/__init__.py
- [X] T006 [P] Setup SQLite storage initialization in w2/db_query/backend/src/storage/sqlite_store.py
- [X] T007 [P] Create FastAPI app with CORS middleware in w2/db_query/backend/src/main.py

### Frontend Setup

- [X] T008 Create frontend project structure at w2/db_query/frontend/
- [X] T009 Initialize React + TypeScript project with Vite in w2/db_query/frontend/
- [X] T010 [P] Configure TailwindCSS in w2/db_query/frontend/tailwind.config.js
- [X] T011 [P] Configure TypeScript strict mode in w2/db_query/frontend/tsconfig.json
- [X] T012 [P] Setup Refine with Ant Design in w2/db_query/frontend/src/App.tsx
- [X] T013 [P] Create API client service in w2/db_query/frontend/src/services/api.ts

### Shared Models & Types

- [X] T014 [P] Create error model in w2/db_query/backend/src/models/error.py
- [X] T015 [P] Create TypeScript type definitions in w2/db_query/frontend/src/types/models.ts

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 2: Core Features (US1 + US2)

**Goal**: Enable users to connect to databases, browse schemas, and execute SQL queries

**Independent Test**: Add a database connection, view its schema, and execute a SELECT query

### User Story 1: Database Connection & Schema Browsing

#### Backend - Connection Management

- [ ] T016 [P] [US1] Create DatabaseConnection model in w2/db_query/backend/src/models/connection.py
- [ ] T017 [P] [US1] Create SchemaMetadata, TableMetadata, ColumnMetadata models in w2/db_query/backend/src/models/metadata.py
- [ ] T018 [US1] Implement ConnectionService with PostgreSQL connection validation in w2/db_query/backend/src/services/connection_service.py
- [ ] T019 [US1] Implement MetadataService with PostgreSQL schema extraction in w2/db_query/backend/src/services/metadata_service.py
- [ ] T020 [US1] Implement SQLite persistence for connections and metadata in w2/db_query/backend/src/storage/sqlite_store.py
- [ ] T021 [US1] Create GET /api/v1/dbs endpoint in w2/db_query/backend/src/api/v1/dbs.py
- [ ] T022 [US1] Create PUT /api/v1/dbs/{name} endpoint in w2/db_query/backend/src/api/v1/dbs.py
- [ ] T023 [US1] Create GET /api/v1/dbs/{name} endpoint in w2/db_query/backend/src/api/v1/dbs.py
- [ ] T024 [US1] Create POST /api/v1/dbs/{name}/refresh endpoint in w2/db_query/backend/src/api/v1/dbs.py
- [ ] T025 [US1] Add error handling for connection failures in w2/db_query/backend/src/api/v1/dbs.py

#### Frontend - Connection Management UI

- [ ] T026 [P] [US1] Create DatabaseList component in w2/db_query/frontend/src/components/DatabaseList.tsx
- [ ] T027 [P] [US1] Create SchemaViewer component in w2/db_query/frontend/src/components/SchemaViewer.tsx
- [ ] T028 [US1] Create database list page in w2/db_query/frontend/src/pages/databases/list.tsx
- [ ] T029 [US1] Create database create page in w2/db_query/frontend/src/pages/databases/create.tsx
- [ ] T030 [US1] Create database show page with schema viewer in w2/db_query/frontend/src/pages/databases/show.tsx
- [ ] T031 [US1] Add error handling and empty states in w2/db_query/frontend/src/pages/databases/

### User Story 2: SQL Query Execution

#### Backend - Query Execution

- [ ] T032 [P] [US2] Create QueryRequest and QueryResult models in w2/db_query/backend/src/models/query.py
- [ ] T033 [US2] Implement SQL validation with sqlglot in w2/db_query/backend/src/services/query_service.py
- [ ] T034 [US2] Implement SELECT-only enforcement in w2/db_query/backend/src/services/query_service.py
- [ ] T035 [US2] Implement multi-statement detection and rejection in w2/db_query/backend/src/services/query_service.py
- [ ] T036 [US2] Implement automatic LIMIT 1000 injection in w2/db_query/backend/src/services/query_service.py
- [ ] T037 [US2] Implement query execution with PostgreSQL in w2/db_query/backend/src/services/query_service.py
- [ ] T038 [US2] Create POST /api/v1/dbs/{name}/query endpoint in w2/db_query/backend/src/api/v1/query.py
- [ ] T039 [US2] Add SQL error handling and user-friendly messages in w2/db_query/backend/src/api/v1/query.py

#### Frontend - Query Execution UI

- [ ] T040 [P] [US2] Create SqlEditor component with Monaco Editor in w2/db_query/frontend/src/components/SqlEditor.tsx
- [ ] T041 [P] [US2] Create QueryResults component with table display in w2/db_query/frontend/src/components/QueryResults.tsx
- [ ] T042 [US2] Create query page with editor and results in w2/db_query/frontend/src/pages/query/index.tsx
- [ ] T043 [US2] Add SQL syntax highlighting and autocomplete in w2/db_query/frontend/src/components/SqlEditor.tsx
- [ ] T044 [US2] Add error display and empty result states in w2/db_query/frontend/src/pages/query/index.tsx

**Checkpoint**: Core features complete - users can connect to databases and execute SQL queries

---

## Phase 3: Advanced Features (US3)

**Goal**: Enable natural language SQL generation using OpenAI

**Independent Test**: Enter a natural language question and get a valid SQL query

### Backend - Natural Language Processing

- [ ] T045 [P] [US3] Create NaturalLanguageContext model in w2/db_query/backend/src/models/query.py
- [ ] T046 [US3] Implement OpenAI SDK integration in w2/db_query/backend/src/services/llm_service.py
- [ ] T047 [US3] Implement schema context preparation for LLM in w2/db_query/backend/src/services/llm_service.py
- [ ] T048 [US3] Implement SQL generation from natural language in w2/db_query/backend/src/services/llm_service.py
- [ ] T049 [US3] Create POST /api/v1/dbs/{name}/query/natural endpoint in w2/db_query/backend/src/api/v1/query.py
- [ ] T050 [US3] Add validation for generated SQL (same rules as manual SQL) in w2/db_query/backend/src/api/v1/query.py

### Frontend - Natural Language UI

- [ ] T051 [P] [US3] Create NaturalLanguageInput component in w2/db_query/frontend/src/components/NaturalLanguageInput.tsx
- [ ] T052 [US3] Add natural language tab to query page in w2/db_query/frontend/src/pages/query/index.tsx
- [ ] T053 [US3] Add generated SQL preview and confirmation in w2/db_query/frontend/src/pages/query/index.tsx
- [ ] T054 [US3] Add loading states for LLM generation in w2/db_query/frontend/src/pages/query/index.tsx

**Checkpoint**: All user stories complete - full feature set implemented

---

## Phase 4: Polish & Documentation

**Purpose**: Final touches and documentation

- [ ] T055 [P] Add README.md for backend in w2/db_query/backend/README.md
- [ ] T056 [P] Add README.md for frontend in w2/db_query/frontend/README.md
- [ ] T057 [P] Add project overview README in w2/db_query/README.md
- [ ] T058 [P] Run type checking (mypy for backend, tsc for frontend)
- [ ] T059 [P] Run linting (ruff for backend, eslint for frontend)
- [ ] T060 Verify all constitution principles are satisfied

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup & Foundation (Phase 1)**: No dependencies - can start immediately
- **Core Features (Phase 2)**: Depends on Phase 1 completion - BLOCKS Phase 3
- **Advanced Features (Phase 3)**: Depends on Phase 2 completion (needs connection and query infrastructure)
- **Polish (Phase 4)**: Depends on all features being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 1 - No dependencies on other stories
- **User Story 2 (P2)**: Depends on US1 (needs database connections to query)
- **User Story 3 (P3)**: Depends on US1 and US2 (needs connections and query validation)

### Within Each Phase

**Phase 1**:
- Backend and Frontend setup can run in parallel
- Models and types can be created in parallel
- SQLite and FastAPI setup are independent

**Phase 2**:
- Backend models (T016, T017, T032) can run in parallel
- Services depend on models being complete
- API endpoints depend on services
- Frontend components (T026, T027, T040, T041) can run in parallel
- Frontend pages depend on components

**Phase 3**:
- Backend LLM model and service can run in parallel with frontend components
- API endpoint depends on LLM service
- Frontend integration depends on API endpoint

### Parallel Opportunities

**Phase 1 Parallel Tasks**:
```bash
# Backend setup (can run together)
T003, T004, T005, T006, T007

# Frontend setup (can run together)
T010, T011, T012, T013

# Models (can run together)
T014, T015
```

**Phase 2 Parallel Tasks**:
```bash
# Backend models (can run together)
T016, T017, T032

# Frontend components (can run together)
T026, T027, T040, T041
```

**Phase 3 Parallel Tasks**:
```bash
# Backend and frontend can start together
T045, T051
```

**Phase 4 Parallel Tasks**:
```bash
# All polish tasks can run together
T055, T056, T057, T058, T059
```

---

## Implementation Strategy

### Simplified 3-Phase Approach

This task list is organized into 3 main implementation phases (plus polish):

1. **Phase 1: Setup & Foundation** - Get the project structure and shared infrastructure ready
2. **Phase 2: Core Features** - Implement US1 (connections) and US2 (queries) together as they're tightly coupled
3. **Phase 3: Advanced Features** - Add US3 (natural language) as an enhancement

### Execution Approach

**Option 1: Sequential (Recommended for single developer)**
1. Complete Phase 1 entirely
2. Complete Phase 2 entirely (delivers MVP with core value)
3. Complete Phase 3 (adds advanced feature)
4. Complete Phase 4 (polish)

**Option 2: Parallel (For team of 2-3)**
1. Developer A: Phase 1 backend
2. Developer B: Phase 1 frontend
3. After Phase 1: Developer A handles backend tasks, Developer B handles frontend tasks
4. Sync at phase boundaries

### MVP Scope

**Minimum Viable Product** = Phase 1 + Phase 2

This delivers:
- ✅ Database connection management
- ✅ Schema browsing
- ✅ SQL query execution with validation
- ✅ Results display

Phase 3 (natural language) can be added later as an enhancement.

---

## Notes

- All tasks follow the checklist format: `- [ ] [ID] [P?] [Story?] Description with file path`
- [P] indicates tasks that can run in parallel (different files, no dependencies)
- [Story] labels (US1, US2, US3) map to user stories from spec.md
- File paths are absolute from repository root
- Constitution compliance verified throughout (type safety, camelCase, no auth, read-only SQL, etc.)
- No test tasks included (not explicitly requested in spec)
- Focus on implementation tasks with clear deliverables

---

## Task Count Summary

- **Phase 1 (Setup)**: 15 tasks
- **Phase 2 (Core Features)**: 29 tasks
  - US1 (Connection & Schema): 16 tasks
  - US2 (SQL Queries): 13 tasks
- **Phase 3 (Advanced Features)**: 10 tasks
  - US3 (Natural Language): 10 tasks
- **Phase 4 (Polish)**: 6 tasks

**Total**: 60 tasks

**Parallel Opportunities**: 20+ tasks can run in parallel within their phases
