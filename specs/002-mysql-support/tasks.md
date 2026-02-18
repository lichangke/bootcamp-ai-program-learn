# Tasks: MySQL Support for DB Query Tool

**Input**: User requirement + reference implementation in `w2/db_query/backend` + baseline design docs in `specs/002-db-query-tool/`  
**Feature Dir**: `D:\GithubCode\bootcamp-ai-program-learn\specs\002-mysql-support`  
**Available Docs in Feature Dir**: none (`[]`)

**Tests**: No mandatory test tasks were generated because TDD/tests were not explicitly requested in this feature input.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare dependency and documentation baseline for MySQL support.

- [X] T001 Add MySQL driver dependency (`pymysql`) and mypy import override in `w2/db_query/backend/pyproject.toml`
- [X] T002 [P] Add MySQL connection examples (including `todo_db` scenario) in `w2/db_query/backend/README.md`
- [X] T003 [P] Create MySQL local verification quickstart notes in `specs/002-mysql-support/quickstart.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build shared dialect handling required by all user stories.

**CRITICAL**: User story work starts only after this phase is complete.

- [X] T004 Create dialect detection helpers and canonical dialect enum in `w2/db_query/backend/src/services/dialect_service.py`
- [X] T005 Refactor URL validation to accept PostgreSQL and MySQL schemes in `w2/db_query/backend/src/services/connection_service.py`
- [X] T006 [P] Update URL field validation error text for dual-dialect support in `w2/db_query/backend/src/models/connection.py`
- [X] T007 Implement per-dialect connector factory (`psycopg2` vs `pymysql`) in `w2/db_query/backend/src/services/connection_service.py`
- [X] T008 [P] Update API wording from PostgreSQL-only to generic database URL in `w2/db_query/backend/src/api/v1/dbs.py`
- [X] T009 [P] Export dialect utilities for service reuse in `w2/db_query/backend/src/services/__init__.py`

**Checkpoint**: Dialect foundation ready for MySQL metadata, query execution, and natural-language SQL generation.

---

## Phase 3: User Story 1 - MySQL Metadata Extraction and Browsing (Priority: P1) MVP

**Goal**: User can save a MySQL connection and browse tables/views/columns metadata just like PostgreSQL.

**Independent Test**: Save a MySQL connection to local `todo_db`, then call `GET /api/v1/dbs/{name}` and verify `todos` metadata is returned with columns.

### Implementation for User Story 1

- [X] T010 [US1] Add dialect parameter propagation to metadata fetch entrypoint in `w2/db_query/backend/src/services/metadata_service.py`
- [X] T011 [US1] Implement MySQL table/view discovery query path in `w2/db_query/backend/src/services/metadata_service.py`
- [X] T012 [US1] Implement MySQL column metadata mapping (`isNullable`, `defaultValue`, `maxLength`, `numericPrecision`) in `w2/db_query/backend/src/services/metadata_service.py`
- [X] T013 [US1] Implement MySQL primary key extraction query path in `w2/db_query/backend/src/services/metadata_service.py`
- [X] T014 [US1] Wire dialect detection into `PUT /dbs/{name}` and `POST /dbs/{name}/refresh` metadata flows in `w2/db_query/backend/src/api/v1/dbs.py`
- [X] T015 [US1] Ensure MySQL metadata snapshots serialize/deserialize correctly in `w2/db_query/backend/src/storage/sqlite_store.py`
- [X] T016 [P] [US1] Update create-connection page labels/placeholders for PostgreSQL/MySQL URLs in `w2/db_query/frontend/src/pages/databases/create.tsx`
- [X] T017 [P] [US1] Update add-connection modal labels/placeholders for dual-dialect URLs in `w2/db_query/frontend/src/App.tsx`

**Checkpoint**: MySQL metadata lifecycle (save -> fetch -> display -> refresh) is functional and independently testable.

---

## Phase 4: User Story 2 - MySQL Read-Only SQL Query Execution (Priority: P2)

**Goal**: User can run MySQL SELECT queries with the same safety guarantees (single statement, SELECT-only, default LIMIT).

**Independent Test**: Execute `SELECT * FROM todos` on saved MySQL connection and receive JSON rows; verify `INSERT INTO ...` is rejected by validator.

### Implementation for User Story 2

- [X] T018 [US2] Make SQL parsing dialect-aware using detected connection dialect in `w2/db_query/backend/src/services/query_service.py`
- [X] T019 [US2] Keep single-statement and SELECT-only guardrails for both PostgreSQL and MySQL in `w2/db_query/backend/src/services/query_service.py`
- [X] T020 [US2] Rebuild default LIMIT injection via sqlglot AST serialization per dialect in `w2/db_query/backend/src/services/query_service.py`
- [X] T021 [US2] Pass detected dialect through `POST /dbs/{name}/query` validation and execution path in `w2/db_query/backend/src/api/v1/query.py`
- [X] T022 [P] [US2] Normalize cursor column type mapping for MySQL result metadata in `w2/db_query/backend/src/services/query_service.py`
- [X] T023 [P] [US2] Improve frontend API error text handling for MySQL query failures in `w2/db_query/frontend/src/services/api.ts`

**Checkpoint**: MySQL manual SQL query flow is safe, validated, and independently testable.

---

## Phase 5: User Story 3 - Natural Language SQL Generation for MySQL (Priority: P3)

**Goal**: User can describe a query in natural language and receive MySQL-compatible SQL before execution.

**Independent Test**: Submit a natural-language prompt for `todo_db`, get generated SQL that passes validator, then execute it successfully through existing query endpoint.

### Implementation for User Story 3

- [X] T024 [US3] Add target dialect parameter to SQL generation interface in `w2/db_query/backend/src/services/llm_service.py`
- [X] T025 [US3] Update LLM system prompt to produce PostgreSQL/MySQL-specific SQL by dialect in `w2/db_query/backend/src/services/llm_service.py`
- [X] T026 [US3] Make fallback SQL generation dialect-aware when LLM is unavailable in `w2/db_query/backend/src/services/llm_service.py`
- [X] T027 [US3] Pass connection dialect into `/query/natural` generation and validation chain in `w2/db_query/backend/src/api/v1/query.py`
- [X] T028 [P] [US3] Update natural-language UX helper text to mention MySQL support in `w2/db_query/frontend/src/App.tsx`

**Checkpoint**: Natural-language to SQL generation supports MySQL and remains guarded by the same read-only validation pipeline.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Update shared docs/contracts and capture validation evidence.

- [X] T029 [P] Update API contract wording/examples from PostgreSQL-only to PostgreSQL+MySQL in `specs/002-db-query-tool/contracts/openapi.yaml`
- [X] T030 [P] Update project overview wording for multi-dialect support in `w2/db_query/README.md`
- [X] T031 [P] Add end-to-end verification steps for local `todo_db` in `specs/002-mysql-support/quickstart.md`
- [X] T032 Run backend quality checks and record outcomes in `specs/002-mysql-support/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1) has no dependencies.
- Foundational (Phase 2) depends on Setup and blocks all user stories.
- User Story phases (Phase 3-5) depend on Foundational completion.
- Polish (Phase 6) depends on all selected user stories being completed.

### User Story Dependencies

- US1 (P1) depends only on Foundational phase.
- US2 (P2) depends on Foundational phase and a saved MySQL connection (delivered by US1 workflow).
- US3 (P3) depends on Foundational phase and available metadata context (delivered by US1 workflow).

### Story Completion Order

1. US1 (metadata support, MVP)
2. US2 (manual SQL execution on MySQL)
3. US3 (natural-language SQL generation for MySQL)

---

## Parallel Opportunities

- Phase 1 parallel tasks: `T002`, `T003`
- Phase 2 parallel tasks: `T006`, `T008`, `T009`
- US1 parallel tasks: `T016`, `T017`
- US2 parallel tasks: `T022`, `T023`
- US3 parallel tasks: `T028`
- Polish parallel tasks: `T029`, `T030`, `T031`

## Parallel Example: User Story 1

```bash
Task T016: Update create page labels/placeholders in w2/db_query/frontend/src/pages/databases/create.tsx
Task T017: Update modal labels/placeholders in w2/db_query/frontend/src/App.tsx
```

## Parallel Example: User Story 2

```bash
Task T022: Normalize MySQL cursor type mapping in w2/db_query/backend/src/services/query_service.py
Task T023: Improve MySQL query error rendering in w2/db_query/frontend/src/services/api.ts
```

## Parallel Example: User Story 3

```bash
Task T028: Update natural-language UX helper text in w2/db_query/frontend/src/App.tsx
Task T026: Make fallback SQL generation dialect-aware in w2/db_query/backend/src/services/llm_service.py
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1 (Setup)
2. Complete Phase 2 (Foundational)
3. Complete Phase 3 (US1)
4. Validate MySQL metadata extraction against local `todo_db`
5. Demo/release MVP

### Incremental Delivery

1. Deliver US1 for MySQL connection + metadata browsing
2. Add US2 for safe MySQL SQL execution
3. Add US3 for dialect-aware natural language SQL generation
4. Finish with Phase 6 docs/contracts/verification updates

### Team Parallel Strategy

1. One developer finishes Phase 1-2 foundation work.
2. Then split by story:
3. Developer A: US1 backend metadata
4. Developer B: US2 validator and query endpoint flow
5. Developer C: US3 LLM prompt/fallback updates
6. Frontend polish tasks (`T016`, `T017`, `T023`, `T028`) can run in parallel with backend story work.

---

## Notes

- All checklist entries follow the required format: checkbox + task ID + optional `[P]` + optional `[USx]` + actionable description with file path.
- No task is left without a concrete file target.
- Tasks are intentionally scoped so each user story can be completed and validated independently.
