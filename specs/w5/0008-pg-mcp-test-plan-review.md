**Test Plan Review: `0007-pg-mcp-test-plan.md`**

**Scope Reviewed**
- Primary: `specs/w5/0007-pg-mcp-test-plan.md:1`
- Compared against: `specs/w5/0002-pg-mcp-design.md:1`, `specs/w5/0004-pg-mcp-impl-plan.md:1`

**Summary of Strengths**
- Test plan has clear layered structure (unit/integration/E2E/security/perf) and explicit pyramid intent: `specs/w5/0007-pg-mcp-test-plan.md:23`.
- Uses test case IDs + priorities, which helps triage and traceability: `specs/w5/0007-pg-mcp-test-plan.md:90`.
- Includes CI/CD section and sample workflow baseline: `specs/w5/0007-pg-mcp-test-plan.md:851`.
- Includes practical non-functional dimensions (security + performance), not only functional checks: `specs/w5/0007-pg-mcp-test-plan.md:735`.

**Issues Found (Severity-Ranked)**

- **Critical — Core test examples conflict with design interfaces, so many samples are not executable as written**
  - `SQLValidator` in design requires config + returns `ValidationResult(is_safe=...)`: `specs/w5/0002-pg-mcp-design.md:474`, `specs/w5/0002-pg-mcp-design.md:483`.
  - Test plan uses `SQLValidator()` + expects exceptions/`is_valid`/`sanitized_sql`: `specs/w5/0007-pg-mcp-test-plan.md:221`, `specs/w5/0007-pg-mcp-test-plan.md:227`, `specs/w5/0007-pg-mcp-test-plan.md:241`.
  - `SQLExecutor.execute` signature in design is `(db_name, sql, limit)`: `specs/w5/0002-pg-mcp-design.md:683`; test examples call `execute(sql)` and initialize executor differently: `specs/w5/0007-pg-mcp-test-plan.md:300`, `specs/w5/0007-pg-mcp-test-plan.md:312`.
  - `SchemaService`/`LLMService` signatures also mismatch design: `specs/w5/0002-pg-mcp-design.md:882`, `specs/w5/0002-pg-mcp-design.md:1030`, `specs/w5/0007-pg-mcp-test-plan.md:360`, `specs/w5/0007-pg-mcp-test-plan.md:447`.
  - `QueryRequest` field name mismatch (`query` vs `question`): `specs/w5/0002-pg-mcp-design.md:1160`, `specs/w5/0007-pg-mcp-test-plan.md:504`.

- **High — Completeness gap vs implementation plan: key required test domains missing**
  - Impl plan explicitly requires AppContext/lifespan/tool tests: `specs/w5/0004-pg-mcp-impl-plan.md:579`, `specs/w5/0004-pg-mcp-impl-plan.md:640`, `specs/w5/0004-pg-mcp-impl-plan.md:703`.
  - Test plan has no dedicated `test_context.py` / `test_lifespan.py` / `test_tool.py` equivalents; only coarse E2E lifecycle mention: `specs/w5/0007-pg-mcp-test-plan.md:678`.

- **High — Traceability matrix in test plan is incomplete relative to design/impl scope**
  - Test plan matrix omits FR-004, FR-009, NFR-001, NFR-003, NFR-006: `specs/w5/0007-pg-mcp-test-plan.md:949`.
  - Impl traceability expects these to be validated: `specs/w5/0004-pg-mcp-impl-plan.md:904`, `specs/w5/0004-pg-mcp-impl-plan.md:908`, `specs/w5/0004-pg-mcp-impl-plan.md:909`, `specs/w5/0004-pg-mcp-impl-plan.md:912`.

- **High — CI/CD workflow is incomplete for stated testing strategy**
  - Integration/security jobs lack Python setup and dependency install steps: `specs/w5/0007-pg-mcp-test-plan.md:873`, `specs/w5/0007-pg-mcp-test-plan.md:887`.
  - No E2E job and no performance schedule despite section claims: `specs/w5/0007-pg-mcp-test-plan.md:842`, `specs/w5/0007-pg-mcp-test-plan.md:848`.
  - Plan mentions real Claude Desktop for E2E, which is not CI-friendly: `specs/w5/0007-pg-mcp-test-plan.md:53`.

- **High — Security testing depth is not sufficient for design’s 3-layer model**
  - Design includes prompt-level defense and blocked-function/construct coverage: `specs/w5/0002-pg-mcp-design.md:1446`, `specs/w5/0002-pg-mcp-design.md:165`, `specs/w5/0002-pg-mcp-design.md:173`.
  - Test plan has SQL injection basics, but no explicit prompt-injection tests, blocked-function matrix (`pg_sleep`, `pg_read_file`, etc.), or subquery-write bypass tests: `specs/w5/0007-pg-mcp-test-plan.md:743`.

- **Medium — Some example tests are logically flawed even before implementation**
  - `server_params` scope bug in E2E snippet (`test_query_execution` uses undefined variable): `specs/w5/0007-pg-mcp-test-plan.md:692`, `specs/w5/0007-pg-mcp-test-plan.md:709`.
  - Integration schema example uses executor to run `CREATE TABLE`, conflicting with read-only model: `specs/w5/0007-pg-mcp-test-plan.md:600`, `specs/w5/0002-pg-mcp-design.md:1462`.
  - Mock patching order may miss initialization path in executor unit sample: `specs/w5/0007-pg-mcp-test-plan.md:299`, `specs/w5/0007-pg-mcp-test-plan.md:307`.

- **Medium — Test pyramid numbers and concrete case inventory are inconsistent**
  - Declared target says `100+` unit and `20-30` integration: `specs/w5/0007-pg-mcp-test-plan.md:25`.
  - Enumerated tables are materially below those values (inference from listed case tables across §3/§4).

- **Low — Coverage goals are aspirational but not operationalized**
  - Module/feature coverage percentages are defined: `specs/w5/0007-pg-mcp-test-plan.md:936`.
  - Workflow does not enforce `--cov-fail-under` thresholds: `specs/w5/0007-pg-mcp-test-plan.md:870`.

**Specific Recommendations for Improvement**
- Align all code examples to the design contract first (validator/executor/schema/llm/request fields) and regenerate snippets from runnable skeleton tests.
- Add a **requirements-to-tests traceability table** that includes FR-004/FR-009/NFR-001/NFR-003/NFR-006, matching impl matrix.
- Add dedicated suites for:
  - `context` and `lifespan` lifecycle behavior (success + partial-failure cleanup),
  - `query_database` tool logic (`return_mode`, limit clamping, structured error mapping).
- Fix CI workflow by adding setup/install steps to every job and adding explicit E2E/perf strategy:
  - E2E split into CI-safe smoke + optional manual full-client run,
  - perf on schedule/manual trigger, not blocking PR by default.
- Add security-specific suites for:
  - prompt injection attempts,
  - blocked functions/constructs (`pg_sleep`, `set_config`, `SELECT INTO`, `LOCK`, `COPY`),
  - subquery and nested bypass attempts,
  - secret leakage checks in logs/errors.

**Missing Test Scenarios (Concrete)**
- `query_database` input validation: invalid `return_mode`, `limit > max_rows_limit`, missing default database.
- Typed error mapping assertions: `DB_NOT_FOUND`, `SCHEMA_NOT_READY`, `QUERY_TIMEOUT`, `SQL_GENERATION_ERROR`, generic fallback.
- `SQLExecutor._ensure_limit_via_ast` behavior: existing lower/higher LIMIT, parse-fallback path.
- `SchemaService` cache behavior: `auto_refresh=True/False`, `is_cache_expired`, `invalidate_cache`.
- `ErrorResponse.model_dump()` exact schema + UTC timestamp format.
- LLM retry policy determinism: backoff timing/jitter bounds and non-retryable HTTP status handling.
- Multi-database routing and default DB selection (`default_database` property logic).
- Read-only enforcement at DB/session level and write-attempt rejection path.
- CI reproducibility checks: markers, fixture isolation, deterministic seed/data setup.

**Overall Assessment**
- **Current rating: Needs major revision before execution readiness.**
- The plan has a strong structure and intent, but it is **not yet fully executable or traceably complete** against the design/implementation baseline.
- After interface alignment + missing T7/T8/security/CI work, this can become a solid, production-grade test plan.

If you want, I can draft a **revised v1.1 test plan skeleton** (with corrected APIs, full traceability matrix, and CI-ready job split) directly in `specs/w5/0007-pg-mcp-test-plan.md`.