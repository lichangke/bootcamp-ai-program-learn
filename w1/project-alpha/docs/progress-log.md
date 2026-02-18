# Progress Log

## 2026-02-14

- Initialized Day 1 skeleton for backend and frontend.
- Added health endpoint and baseline project tooling.
- Added Day 2 migration toolchain (Alembic) and first PostgreSQL schema migration.
- Implemented repository CRUD skeleton for tickets, tags, and ticket-tag relations.
- Added Day 3 ticket API endpoints and ticket service business rules.
- Added unit tests for ticket service and API route behavior.
- Added Day 4 tag API endpoints and tag service validation/conflict handling.
- Added ticket list filtering/search/pagination API (`tag_id`, `q`, `status`, `page`, `page_size`).
- Added repository/service/API tests for tag CRUD and ticket list query behavior.

## 2026-02-18

- Executed Day 5/6/7 Playwright smoke test in `w1/project-alpha/frontend` via `npm run e2e`.
- Fixed unstable assertions in `frontend/tests/e2e/smoke.spec.ts`:
  - Replaced ambiguous `getByText("done")`/`getByText("open")` checks with action-button state checks (`Reopen`/`Complete`).
  - Added status filter switch back to `open` after `Reopen` to align assertions with real list-filter behavior.
- Final Playwright result: `1 passed` (`tests/e2e/smoke.spec.ts`, run time ~4.0s).
- Day 5 status: Completed.
- Day 5 delivered scope: `TicketListPage`, `TicketEditorDialog`, `TagManagerDialog`, TanStack Query integration, ticket/tag CRUD flow, complete/reopen action flow.
- Day 6 status: Completed.
- Day 6 delivered scope: search debounce (300ms), filter linkage, loading/error/empty states, delete confirmation, toast feedback, optimistic update rollback for mutation failures.
- Day 7 status: Completed.
- Day 7 delivered scope: backend API integration tests, backend list performance test (10k sample data, p95 target), frontend component tests, Playwright E2E smoke coverage.
- Day 7 verification result summary: backend test/lint and frontend lint/build/unit/E2E all passed in local validation runs.
- Added repeatable seed dataset in `seed.sql` (50 tickets, 50 tags, 150 links).
- Added `backend-db-seed`, `backend-dev`, and `frontend-dev` make targets.
- Added light/dark theme toggle with persisted preference in frontend UI.
- Day 8 status: Completed.
- Day 8 delivered scope: acceptance review, docs freeze, open-items registration.
- Added final acceptance and handoff docs:
  - `docs/final-acceptance.md`
  - `docs/open-items.md`
- Final Day 8 verification run on 2026-02-18:
  - backend: `python -m ruff check .` + `python -m pytest -q` -> pass
  - frontend: `npm run lint` + `npm run build` + `npm run test:run` + `npm run e2e` -> pass
