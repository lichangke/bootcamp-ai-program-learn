# Tasks: 数据库查询工具

**Input**: Design documents from `D:/GithubCode/bootcamp-ai-program-learn/specs/001-db-query-tool/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/openapi.yaml`, `quickstart.md`

**Tests**: 未显式要求 TDD，本任务清单以实现为主，并通过 quickstart 冒烟验证独立验收。

**Type Checks**: 包含后端与前端严格类型检查配置任务（符合 constitution）。

**Organization**: 受“任务较简单，phase 不超过 3 个”约束，采用 3-phase 结构，并在 Phase 2 内按用户故事分组。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无未完成依赖）
- **[Story]**: 用户故事标签（`[US1]`、`[US2]`、`[US3]`）
- 每个任务都包含明确文件路径

## Phase 1: Setup + Foundational (Shared Infrastructure)

**Purpose**: 完成项目脚手架、基础中间件、数据持久化与类型规范，阻塞后续全部用户故事。

- [ ] T001 创建前后端目录骨架与入口文件 `w2/db_query/backend/src/main.py`
- [ ] T002 初始化后端依赖（FastAPI/Pydantic/sqlglot/OpenAI/psycopg）到 `w2/db_query/backend/pyproject.toml`
- [ ] T003 [P] 初始化前端依赖（React/refine/antd/tailwind/monaco）到 `w2/db_query/frontend/package.json`
- [ ] T004 [P] 启用前端 TypeScript strict 配置 `w2/db_query/frontend/tsconfig.json`
- [ ] T005 [P] 配置后端环境与路径设置（`OPENAI_API_KEY`、`~/.db_query/db_query.db`）到 `w2/db_query/backend/src/core/settings.py`
- [ ] T006 实现 FastAPI 应用与全开放 CORS 中间件于 `w2/db_query/backend/src/main.py`
- [ ] T007 [P] 定义 Pydantic 基类与 camelCase 序列化策略于 `w2/db_query/backend/src/models/base.py`
- [ ] T008 [P] 实现 SQLite 初始化与连接管理于 `w2/db_query/backend/src/repositories/sqlite_store.py`
- [ ] T009 实现统一错误响应处理（camelCase）于 `w2/db_query/backend/src/api/error_handlers.py`
- [ ] T010 实现前端统一 API 客户端与类型化请求封装于 `w2/db_query/frontend/src/services/apiClient.ts`

**Checkpoint**: 基础能力就绪，US1/US2/US3 可按优先级推进。

---

## Phase 2: User Stories (Priority-Ordered Delivery)

### User Story 1 - 连接数据库并查看元数据 (P1) 🎯 MVP

**Goal**: 用户可添加连接、验证可达、存储并查看表/视图元数据。

**Independent Test**: 提交有效连接后可看到表/视图；提交无效连接返回错误且不保存。

- [ ] T011 [P] [US1] 定义 `DbConnection` 与 `SchemaMetadata` 模型于 `w2/db_query/backend/src/models/connection.py`
- [ ] T012 [P] [US1] 实现 PostgreSQL 元数据抓取服务于 `w2/db_query/backend/src/services/postgres_metadata_service.py`
- [ ] T013 [P] [US1] 实现元数据 LLM 归一化服务于 `w2/db_query/backend/src/services/metadata_llm_service.py`
- [ ] T014 [US1] 实现连接信息持久化仓储（upsert/get/list）于 `w2/db_query/backend/src/repositories/connection_repository.py`
- [ ] T015 [US1] 实现元数据版本化仓储（save/latest/refresh）于 `w2/db_query/backend/src/repositories/metadata_repository.py`
- [ ] T016 [US1] 实现数据库连接业务服务（连通性校验+metadata 刷新）于 `w2/db_query/backend/src/services/database_service.py`
- [ ] T017 [US1] 实现 `GET /api/v1/dbs`、`PUT /api/v1/dbs/{name}`、`GET /api/v1/dbs/{name}` 于 `w2/db_query/backend/src/api/routes/databases.py`
- [ ] T018 [US1] 实现连接管理与元数据展示页面于 `w2/db_query/frontend/src/pages/databases/DatabaseListPage.tsx`
- [ ] T019 [US1] 实现前端数据库资源服务与页面联动于 `w2/db_query/frontend/src/services/databases.ts`

**Checkpoint**: MVP 可演示（连接 + 元数据）。

### User Story 2 - 执行只读 SQL 查询 (P2)

**Goal**: 用户可执行只读 SQL，系统强制语法与只读限制并返回 JSON 表格数据。

**Independent Test**: 合法 `SELECT` 成功返回；非只读或语法错误被拒绝；无 `LIMIT` 自动补 `LIMIT 1000`。

- [ ] T020 [P] [US2] 定义 `SqlQueryRequest` 与 `QueryResponse` 模型于 `w2/db_query/backend/src/models/query.py`
- [ ] T021 [P] [US2] 实现 sqlglot 只读校验与 `LIMIT 1000` 注入于 `w2/db_query/backend/src/services/sql_guard_service.py`
- [ ] T022 [US2] 实现 PostgreSQL 查询执行与 JSON 行列映射于 `w2/db_query/backend/src/services/query_service.py`
- [ ] T023 [US2] 实现 `POST /api/v1/dbs/{name}/query` 于 `w2/db_query/backend/src/api/routes/query.py`
- [ ] T024 [US2] 实现 Monaco SQL 编辑器组件于 `w2/db_query/frontend/src/components/sql/SqlEditorPanel.tsx`
- [ ] T025 [US2] 实现查询结果表格渲染组件于 `w2/db_query/frontend/src/components/sql/QueryResultTable.tsx`
- [ ] T026 [US2] 实现 SQL 查询页面与接口联动于 `w2/db_query/frontend/src/pages/query/SqlQueryPage.tsx`

**Checkpoint**: US1 + US2 可独立运行且互不阻塞。

### User Story 3 - 自然语言生成查询 (P3)

**Goal**: 用户输入自然语言，系统基于 metadata 生成可编辑 SQL，并可继续执行。

**Independent Test**: 输入自然语言后返回 SQL 预览；失败可提示并回退手写 SQL；确认后可执行。

- [ ] T027 [P] [US3] 定义 `NaturalQueryRequest` 与 `NaturalQueryResponse` 模型于 `w2/db_query/backend/src/models/natural_query.py`
- [ ] T028 [P] [US3] 实现 NL2SQL prompt 构造（注入表/视图上下文）于 `w2/db_query/backend/src/services/nl2sql_prompt_service.py`
- [ ] T029 [US3] 实现 OpenAI NL2SQL 生成服务于 `w2/db_query/backend/src/services/nl2sql_service.py`
- [ ] T030 [US3] 实现 `POST /api/v1/dbs/{name}/query/natural` 于 `w2/db_query/backend/src/api/routes/natural_query.py`
- [ ] T031 [US3] 实现自然语言输入与 SQL 预览组件于 `w2/db_query/frontend/src/components/natural/NaturalQueryPanel.tsx`
- [ ] T032 [US3] 实现自然语言查询页面与“编辑后执行”联动于 `w2/db_query/frontend/src/pages/query/NaturalQueryPage.tsx`

**Checkpoint**: 三个用户故事全部可独立验收。

---

## Phase 3: Polish & Cross-Cutting Concerns

**Purpose**: 完成跨故事质量项、文档与冒烟验证。

- [ ] T033 [P] 增加后端请求日志与 requestId 中间件于 `w2/db_query/backend/src/core/logging.py`
- [ ] T034 [P] 增加前端统一错误边界与错误提示映射于 `w2/db_query/frontend/src/app/ErrorBoundary.tsx`
- [ ] T035 编写 API 冒烟脚本（覆盖 5 个核心接口）于 `w2/db_query/scripts/smoke-test.ps1`
- [ ] T036 更新实现说明与运行文档于 `w2/db_query/README.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: 无依赖，立即开始；完成前阻塞所有用户故事。
- **Phase 2**: 依赖 Phase 1 完成；内部按 P1 → P2 → P3 推荐推进。
- **Phase 3**: 依赖 Phase 2 目标故事完成。

### User Story Dependencies (Completion Graph)

- **US1 (P1)**: 起点故事，完成后提供连接与 metadata 基础。
- **US2 (P2)**: 依赖 US1 的连接与 metadata。
- **US3 (P3)**: 依赖 US1 的 metadata；复用 US2 的 SQL 执行链路。

**Graph**: `US1 -> US2 -> US3`

### Parallel Opportunities

- **Phase 1**: T003/T004/T005/T007/T008 可并行。
- **US1**: T011/T012/T013 可并行，随后汇合到 T016/T017。
- **US2**: T020/T021 可并行；前端 T024/T025 可并行。
- **US3**: T027/T028 可并行；前端 T031 可与后端 T029 并行。
- **Phase 3**: T033 与 T034 可并行。

---

## Parallel Example: User Story 1

```bash
Task: "T011 [US1] in w2/db_query/backend/src/models/connection.py"
Task: "T012 [US1] in w2/db_query/backend/src/services/postgres_metadata_service.py"
Task: "T013 [US1] in w2/db_query/backend/src/services/metadata_llm_service.py"
```

## Parallel Example: User Story 2

```bash
Task: "T020 [US2] in w2/db_query/backend/src/models/query.py"
Task: "T021 [US2] in w2/db_query/backend/src/services/sql_guard_service.py"
Task: "T024 [US2] in w2/db_query/frontend/src/components/sql/SqlEditorPanel.tsx"
Task: "T025 [US2] in w2/db_query/frontend/src/components/sql/QueryResultTable.tsx"
```

## Parallel Example: User Story 3

```bash
Task: "T027 [US3] in w2/db_query/backend/src/models/natural_query.py"
Task: "T028 [US3] in w2/db_query/backend/src/services/nl2sql_prompt_service.py"
Task: "T031 [US3] in w2/db_query/frontend/src/components/natural/NaturalQueryPanel.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1。
2. 完成 US1（T011-T019）。
3. 按 quickstart 冒烟验证连接与 metadata 展示。
4. 通过后即可 MVP 演示。

### Incremental Delivery

1. `US1`：先交付连接与 metadata。
2. `US2`：增量交付只读 SQL 查询能力。
3. `US3`：最后交付自然语言生成 SQL。
4. 每完成一个故事即执行对应独立验收。

### Completeness Check

- 每个用户故事均包含：模型、服务、API、前端集成任务。
- 每个用户故事均可按其 independent test 单独验证。
- 全部任务均为严格 checklist 格式：`- [ ] Txxx [P?] [US?] 描述 + 文件路径`。
