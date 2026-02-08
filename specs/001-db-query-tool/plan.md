# Implementation Plan: 数据库查询工具

**Branch**: `001-db-query-tool` | **Date**: 2026-02-08 | **Spec**: `D:/GithubCode/bootcamp-ai-program-learn/specs/001-db-query-tool/spec.md`
**Input**: Feature specification from `D:/GithubCode/bootcamp-ai-program-learn/specs/001-db-query-tool/spec.md`

## Summary

构建一个无认证的数据库查询 Web 应用：用户可登记 PostgreSQL 连接、缓存并展示表/视图元数据、执行受限只读 SQL（自动补全 `LIMIT 1000`）、并通过自然语言生成 SQL。后端采用 Python + FastAPI + sqlglot + OpenAI SDK，并将连接与元数据持久化到 `~/.db_query/db_query.db`；前端采用 React + refine 5 + Tailwind + Ant Design + Monaco Editor。

## Technical Context

**Language/Version**: Python 3.12（uv 管理）、TypeScript 5.x（React 19）
**Primary Dependencies**: FastAPI, Pydantic v2, sqlglot, OpenAI Python SDK, psycopg, SQLite (`sqlite3`/`aiosqlite`), React, refine 5, Ant Design, Tailwind CSS 4, Monaco Editor (`@monaco-editor/react`)
**Storage**: 元数据与连接信息存储于 `~/.db_query/db_query.db`（SQLite）；业务查询目标库为 PostgreSQL
**Testing**: 后端 `pytest` + `pytest-asyncio` + `httpx`; 前端 `vitest` + React Testing Library
**Target Platform**: 本地或内网部署的 Web 应用（后端支持 Linux/macOS/Windows，前端支持现代 Chromium/Firefox/Safari）
**Project Type**: Web application（frontend + backend）
**Performance Goals**: 90% 用户 30 秒完成连接并看到元数据；95% 合法只读查询 5 秒内返回（与 spec SC 对齐）
**Constraints**: 仅允许 `SELECT`；缺失 `LIMIT` 时自动补 `LIMIT 1000`；CORS 允许所有 origin；对外 JSON 均为 camelCase；禁用认证；OpenAI Key 仅从 `OPENAI_API_KEY` 读取
**Scale/Scope**: 初始范围为单租户工具型应用，支持 10-50 个已保存连接、每次查询最多返回 1000 行

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Phase 0 前置检查

- ✅ 后端仅使用 Python（FastAPI + Pydantic）
- ✅ 前端仅使用 TypeScript（React + refine 5）
- ✅ 设计要求前后端进行类型约束与检查
- ✅ 后端请求/响应/领域模型统一由 Pydantic 定义
- ✅ 对外 JSON 统一 camelCase（含错误响应）
- ✅ 不实现认证/授权/登录
- **Gate Result**: PASS

### Phase 1 设计后复核

- ✅ `data-model.md` 定义全部核心 Pydantic 实体与校验规则
- ✅ `contracts/openapi.yaml` 仅暴露匿名接口，未引入认证机制
- ✅ 合约输出字段采用 camelCase 命名
- ✅ 约束了 SQL 安全边界（只读 + limit 注入）
- **Gate Result**: PASS

## Project Structure

### Documentation (this feature)

```text
D:/GithubCode/bootcamp-ai-program-learn/specs/001-db-query-tool/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
└── tasks.md
```

### Source Code (repository root)

```text
D:/GithubCode/bootcamp-ai-program-learn/w2/db_query
├── backend/
│   ├── pyproject.toml
│   ├── src/
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
│   │   └── repositories/
│   └── tests/
└── frontend/
    ├── package.json
    ├── src/
    │   ├── app/
    │   ├── pages/
    │   ├── components/
    │   ├── services/
    │   └── types/
    └── tests/
```

**Structure Decision**: 采用前后端分离 Web 应用结构（`backend/` + `frontend/`），以满足 FastAPI 接口、React/refine UI 与契约并行演进需求。

## Complexity Tracking

无宪法违规项，无需填写复杂度豁免。

