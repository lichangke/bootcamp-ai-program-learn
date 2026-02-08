# Research: 数据库查询工具

**Feature**: `D:/GithubCode/bootcamp-ai-program-learn/specs/001-db-query-tool/spec.md`  
**Date**: 2026-02-08

## Decision 1: 后端技术栈采用 FastAPI + Pydantic v2 + uv

- **Decision**: 使用 Python 3.12、`uv` 管理依赖与运行、FastAPI 提供 REST API、Pydantic v2 统一请求/响应/领域模型。
- **Rationale**: 与宪法 CC-001/CC-003 完全一致；FastAPI 天然支持 OpenAPI；Pydantic 易于强约束并可统一 camelCase 序列化。
- **Alternatives considered**:
  - Flask + marshmallow：模型与校验分散，不如 Pydantic 一致。
  - Django REST Framework：对该工具型服务偏重。

## Decision 2: SQL 安全策略采用 sqlglot AST 校验 + 强制只读

- **Decision**: 使用 `sqlglot` 解析用户 SQL，要求 AST 全部为 `SELECT`，拒绝 DDL/DML、多语句与危险函数；若未带 `LIMIT` 则自动注入 `LIMIT 1000`。
- **Rationale**: 明确满足 FR-007/FR-008，避免仅靠字符串匹配导致的绕过风险。
- **Alternatives considered**:
  - `sqlparse`：更偏格式化，语义校验能力弱。
  - 正则匹配 `SELECT`：无法可靠识别嵌套或注释绕过。

## Decision 3: 元数据来源与存储采用 PostgreSQL introspection + SQLite 缓存

- **Decision**: 针对 PostgreSQL 查询 `information_schema` 与 `pg_catalog` 收集表/视图/字段，随后由 LLM 归一化为 JSON，并存到 `~/.db_query/db_query.db`。
- **Rationale**: 对齐 FR-013/FR-014/FR-016；缓存避免重复探测，提升 NL2SQL 上下文复用效率。
- **Alternatives considered**:
  - 每次实时 introspection：开销大且延迟高。
  - 直接原始结构入库：跨版本/跨查询路径一致性较差。

## Decision 4: LLM 集成采用 OpenAI SDK + 受控 Prompt

- **Decision**: 使用 OpenAI Python SDK，API Key 从 `OPENAI_API_KEY` 读取；分别为“元数据 JSON 归一化”和“自然语言生成 SQL”定义独立 prompt 模板。
- **Rationale**: 满足用户给定约束；将元数据作为显式上下文能提升 SQL 可执行率（FR-015）。
- **Alternatives considered**:
  - 其他 LLM 供应商：不满足当前指定条件。
  - 前端直连 LLM：泄露 key 风险高且难审计。

## Decision 5: API 契约采用 OpenAPI 3.1 + camelCase 响应

- **Decision**: 契约文件使用 OpenAPI 3.1，路径按用户给定：
  - `GET /api/v1/dbs`
  - `PUT /api/v1/dbs/{name}`
  - `GET /api/v1/dbs/{name}`
  - `POST /api/v1/dbs/{name}/query`
  - `POST /api/v1/dbs/{name}/query/natural`
- **Rationale**: 可直接驱动前端 TS 类型生成与后端测试；统一 camelCase 对齐 CC-004。
- **Alternatives considered**:
  - GraphQL：超出当前需求且增加学习成本。

## Decision 6: 前端采用 React + refine 5 + Ant Design + Tailwind + Monaco

- **Decision**: 使用 React + TypeScript strict，refine 5 作为数据驱动 UI 框架，Ant Design 组件，Tailwind 做布局样式，Monaco 作为 SQL Editor。
- **Rationale**: 与用户输入完全一致；refine 便于快速构建 CRUD/资源页面，Monaco 提供 SQL 高亮与编辑体验。
- **Alternatives considered**:
  - Material UI：与用户指定组件库不一致。
  - CodeMirror：可行但不符合指定编辑器。

## Decision 7: CORS 与鉴权策略

- **Decision**: 后端开启 CORS 且 `allowOrigins=["*"]`，不实现任何认证/授权。
- **Rationale**: 对齐用户明确要求与宪法 CC-005。
- **Alternatives considered**:
  - 白名单 Origin：更安全但不符合当前明确要求。
  - API Token：违反无认证约束。

## Clarification Resolution Summary

Technical Context 中不存在未决 `NEEDS CLARIFICATION` 项；所有关键技术选型、集成边界与约束在本文件中已明确并可进入 Phase 1 设计。
