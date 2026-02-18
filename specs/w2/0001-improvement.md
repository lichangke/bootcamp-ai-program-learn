# 0001 Improvement: DB Query Backend 多数据库可扩展架构设计

## 1. 背景与目标

当前 `w2/db_query/backend` 在支持 PostgreSQL 后又加入了 MySQL。功能可用，但数据库方言相关逻辑分散在多个 service/router 中。每新增一种数据库，都需要修改多处既有代码，违反 Open-Close Principle（对扩展开放、对修改关闭）。

本设计目标：

1. 引入统一数据库适配接口（interface / protocol）
2. 将“方言差异”隔离到适配器层，业务层不关心具体数据库
3. 让新增数据库（如 SQLite/MSSQL/ClickHouse）只需新增 adapter 和注册，不改核心流程
4. 保持现有 API 行为基本不变，降低迁移风险

---

## 2. 现状问题（架构评审）

### 2.1 方言判断散落，多处 if/else

- `connection_service.py` 中 `_connect_with_dialect` 用 `if dialect == ...` 选择驱动
- `metadata_service.py` 每个方法内都有 PG/MySQL 分支 SQL
- `llm_service.py` fallback 和 prompt 内有方言分支
- router 层（`api/v1/dbs.py`, `api/v1/query.py`）需要显式 detect dialect 并传递

结果：新增数据库时会触发横向修改，难以控制回归范围。

### 2.2 Router 同时承担编排和方言细节传递

`api` 路由不应知道数据库方言细节，但当前要负责 `detect_dialect` 和参数传递。  
这让 API 层与具体实现耦合，影响单一职责。

### 2.3 “连接能力 + 元数据能力 + SQL 校验能力”未抽象为可替换组件

当前 service 多为通用类 + dialect 参数，缺少接口边界：

- 没有 `DatabaseAdapter` 接口
- 没有 `AdapterRegistry` 统一路由 scheme -> adapter
- 没有 `MetadataExtractor` / `SqlDialectPolicy` 的可插拔机制

### 2.4 连接模型未显式存储 dialect

`DatabaseConnection` 当前只存 URL。虽然可从 URL 推断，但每次推断会重复逻辑，也不利于后续支持“同一驱动多种 URL 变体”。

---

## 3. 设计原则（SOLID + OCP）

### 3.1 SRP（单一职责）

- API 层：只做请求/响应、异常映射
- Application 层（用例服务）：编排流程
- Adapter 层：处理具体数据库差异（连接、metadata、SQL policy）

### 3.2 OCP（开闭）

新增数据库时：

1. 新增一个 adapter 类（例如 `SqlServerAdapter`）
2. 在 registry 注册（或 entrypoint 自动发现）
3. 不修改 query/metadata 主流程

### 3.3 LSP（里式替换）

所有 adapter 实现统一接口，调用方只依赖接口，不依赖具体数据库类型。

### 3.4 ISP（接口隔离）

将大接口拆分为职责明确的小接口：连接、元数据、SQL policy、LLM 方言提示。

### 3.5 DIP（依赖倒置）

高层 `DatabaseOrchestrator` 依赖 `Protocol`，通过 registry/工厂注入具体实现。

---

## 4. 目标架构

## 4.1 分层

```text
api/
  v1/
    dbs.py
    query.py

application/
  database_orchestrator.py   # 编排连接、metadata、query、natural-query

domain/
  interfaces/
    db_adapter.py            # Protocol/interface
    metadata_extractor.py
    sql_policy.py

infrastructure/
  adapters/
    postgres/
      adapter.py
      metadata_extractor.py
      sql_policy.py
    mysql/
      adapter.py
      metadata_extractor.py
      sql_policy.py
  registry.py                # URL scheme -> adapter factory
  storage/
    sqlite_store.py

services/
  llm_service.py             # 保留，但改为接收 adapter 提供的 dialect hints
```

---

## 4.2 核心接口定义（建议）

```python
# domain/interfaces/db_adapter.py
from __future__ import annotations
from typing import Any, Protocol

from src.models.metadata import SchemaMetadata

class DbAdapter(Protocol):
    name: str
    schemes: tuple[str, ...]
    sqlglot_dialect: str

    def validate_url(self, url: str) -> None: ...
    def connect(self, url: str, timeout: int) -> Any: ...
    def test_connection(self, url: str) -> None: ...
    def fetch_metadata(self, connection_name: str, conn: Any) -> SchemaMetadata: ...
    def normalize_column_type(self, raw_type: Any) -> str: ...
    def llm_dialect_label(self) -> str: ...
```

```python
# domain/interfaces/sql_policy.py
from __future__ import annotations
from typing import Protocol

class SqlPolicy(Protocol):
    def validate_readonly_single_statement(self, sql: str) -> str: ...
```

说明：

- `sqlglot_dialect`、`llm_dialect_label` 由 adapter 暴露
- `fetch_metadata` 不再让上层传 dialect
- `normalize_column_type` 解决 cursor description 差异

---

## 4.3 Registry / Factory

```python
# infrastructure/registry.py
class AdapterRegistry:
    def __init__(self) -> None:
        self._by_scheme: dict[str, DbAdapter] = {}

    def register(self, adapter: DbAdapter) -> None:
        for s in adapter.schemes:
            self._by_scheme[s] = adapter

    def resolve_by_url(self, url: str) -> DbAdapter:
        scheme = urlparse(url).scheme.lower()
        try:
            return self._by_scheme[scheme]
        except KeyError as exc:
            raise ConnectionValidationError(f"Unsupported scheme: {scheme}") from exc
```

新增数据库时只做 register，不改应用流程。

---

## 5. 应用编排层（替代 router 里的方言逻辑）

新增 `DatabaseOrchestrator`，对外提供：

1. `upsert_connection_and_metadata(name, url)`
2. `refresh_metadata(name)`
3. `execute_sql(name, sql)`
4. `generate_sql_from_natural(name, prompt)`

其内部流程：

1. 从 storage 取连接
2. registry 解析 adapter
3. 调 adapter + shared service（如 llm_service）
4. 统一错误封装

Router 只调用 orchestrator，不再做 dialect detect 和 if/else。

---

## 6. 数据模型与存储调整建议

### 6.1 Connection 增加 `dialect` 字段

`DatabaseConnection` 增加：

- `dialect: Literal["postgres","mysql", ...]`

收益：

- 减少重复解析 URL
- 便于审计与展示
- 未来支持 URL 别名 scheme 时仍可统一内部 dialect

### 6.2 SQLite schema 迁移

`connections` 表新增 `dialect TEXT NOT NULL DEFAULT 'postgres'`。  
在 `init_storage()` 中加入轻量 migration（检查列是否存在，不存在则 ALTER）。

---

## 7. 迁移方案（分阶段，低风险）

## Phase A: 引入抽象，不改行为

1. 新增 `DbAdapter` Protocol
2. 新增 `PostgresAdapter`、`MySqlAdapter`（内部复用现有 SQL）
3. 新增 `AdapterRegistry` 并在 startup 完成注册

## Phase B: 编排收敛

1. 新增 `DatabaseOrchestrator`
2. 将 `dbs.py` / `query.py` 中方言逻辑迁移到 orchestrator
3. router 只保留请求解析与错误映射

## Phase C: 模型与存储升级

1. `DatabaseConnection` 增加 `dialect`
2. SQLite migration
3. 前端模型可选显示 dialect（非阻塞）

## Phase D: 清理旧逻辑

1. 删除 `ConnectionService.detect_dialect` 及重复 if/else
2. `MetadataService` 转为 adapter 内部职责或被拆分
3. 补充 contract/integration tests

---

## 8. 新增数据库时的开发模板

以 `sqlite` 为例：

1. 新建 `infrastructure/adapters/sqlite/adapter.py`
2. 实现 `DbAdapter` 所有接口
3. 在 registry 注册 `("sqlite",)` scheme
4. 新增 `fixtures` + contract tests
5. 无需修改 router / orchestrator 主流程

---

## 9. 验收标准

1. 新增一种数据库支持时，核心流程文件改动不超过 2 处（理想为 0，只有注册点）
2. `api/v1/dbs.py` 与 `api/v1/query.py` 不包含任何方言 `if/else`
3. 所有 SQL 安全约束在 adapter/sql policy 层统一实现
4. 回归测试覆盖 PostgreSQL + MySQL

---

## 10. 建议的下一步落地任务

1. 创建 `DbAdapter`、`AdapterRegistry`、`DatabaseOrchestrator` 骨架
2. 迁移现有 PG/MySQL 逻辑到两个 adapter
3. 改造 router 调 orchestrator
4. 添加 `dialect` 字段与 SQLite migration
5. 增补单测和 Playwright 冒烟测试

---

## 附：为什么该方案符合 OCP/SOLID

- OCP：新增数据库通过“新增 adapter + 注册”扩展，不修改流程代码
- SRP：API、编排、方言实现职责分离
- DIP：高层依赖接口（Protocol），而非具体 `psycopg2/pymysql`
- ISP：接口按能力拆分，避免巨型 service
- LSP：任一 adapter 可替换，行为契约一致
