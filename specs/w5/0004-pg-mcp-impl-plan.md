# PostgreSQL MCP Server 实现计划

> 版本: 1.0.0
> 创建日期: 2026-02-23
> 状态: 草稿
> 关联设计文档: [0002-pg-mcp-design.md](./0002-pg-mcp-design.md)
> 关联 PRD: [0001-pg-mcp-prd.md](./0001-pg-mcp-prd.md)

---

## 1. 实现概述

### 1.1 目标

将技术设计文档中的架构和模块设计转化为可执行的开发任务，按依赖关系排序，确保每个阶段产出可测试、可验证的增量交付物。

### 1.2 实现策略

采用**自底向上、逐层集成**的策略：

1. **基础层优先**：先搭建项目骨架、配置管理、异常定义等无外部依赖的模块
2. **核心服务层**：实现 SQL 校验器、数据库执行器、Schema 服务等核心业务逻辑
3. **集成层**：实现 LLM 服务、FastMCP Tool 注册、生命周期管理
4. **端到端验证**：集成测试、手动验证、Docker 部署

### 1.3 技术栈确认

| 组件 | 版本要求 | 用途 |
|------|----------|------|
| Python | ≥ 3.12 | 运行时 |
| FastMCP | ≥ 0.1.0 | MCP Server 框架 |
| asyncpg | ≥ 0.29.0 | PostgreSQL 异步驱动 |
| SQLGlot | ≥ 23.0.0 | SQL AST 解析与校验 |
| Pydantic | ≥ 2.0.0 | 数据模型与配置验证 |
| pydantic-settings | ≥ 2.0.0 | 环境变量/配置文件管理 |
| httpx | ≥ 0.27.0 | 异步 HTTP 客户端 (DeepSeek API) |
| PyYAML | ≥ 6.0.0 | YAML 配置文件解析 |
| pytest | ≥ 8.0.0 | 测试框架 |
| pytest-asyncio | ≥ 0.23.0 | 异步测试支持 |
| ruff | ≥ 0.3.0 | 代码检查与格式化 |

---

## 2. 阶段划分

### 总览

| 阶段 | 名称 | 核心产出 | 依赖 |
|------|------|----------|------|
| P0 | 项目初始化与骨架搭建 | 可运行的空项目 | 无 |
| P1 | 配置管理与异常体系 | Settings、类型化异常 | P0 |
| P2 | SQL 安全校验器 | SQLValidator（白名单模式） | P1 |
| P3 | 数据库执行器 | SQLExecutor + 连接池 | P1 |
| P4 | Schema 发现服务 | SchemaService + 缓存 | P3 |
| P5 | 数据模型层 | 请求/响应 Pydantic 模型 | P1 |
| P6 | LLM 服务 | DeepSeek 集成 + 重试 | P4, P5 |
| P7 | 应用上下文与生命周期 | AppContext + lifespan | P2-P6 |
| P8 | FastMCP Tool 注册 | query_database Tool | P7 |
| P9 | 集成测试与端到端验证 | E2E 测试 + Docker | P8 |

---

## 3. 详细任务分解

### P0: 项目初始化与骨架搭建

#### T0.1 创建项目目录结构

创建设计文档中定义的完整目录结构：

```
pg_mcp/
├── __init__.py
├── __main__.py
├── server.py
├── context.py
├── config/
│   ├── __init__.py
│   └── settings.py
├── services/
│   ├── __init__.py
│   ├── llm.py
│   ├── schema.py
│   └── executor.py
├── security/
│   ├── __init__.py
│   └── validator.py
├── models/
│   ├── __init__.py
│   ├── schema.py
│   ├── request.py
│   └── response.py
├── exceptions/
│   ├── __init__.py
│   └── errors.py
└── utils/
    ├── __init__.py
    └── logging.py
```

验收标准：
- 所有 `__init__.py` 文件已创建
- 每个模块文件包含占位 docstring
- `python -c "import pg_mcp"` 可正常执行

#### T0.2 创建 pyproject.toml

按设计文档 §9.1 定义项目元数据和依赖：

```toml
[project]
name = "pg-mcp"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=0.1.0",
    "asyncpg>=0.29.0",
    "sqlglot>=23.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "httpx>=0.27.0",
    "pyyaml>=6.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.3.0",
]
```

验收标准：
- `pip install -e ".[dev]"` 成功安装
- 所有依赖版本可解析

#### T0.3 创建 FastMCP Server 骨架

实现 `pg_mcp/server.py`，创建最小可运行的 FastMCP 实例：

```python
from fastmcp import FastMCP
mcp = FastMCP("pg-mcp-server")
```

实现 `pg_mcp/__main__.py` 入口点（仅启动框架，不含业务逻辑）。

验收标准：
- `python -m pg_mcp` 可启动（即使无 Tool 注册）
- 进程可通过 Ctrl+C 正常退出

#### T0.4 配置开发工具链

- 创建 `ruff.toml`（行长 120，Python 3.12 target）
- 创建 `pytest.ini` 或在 `pyproject.toml` 中配置 pytest
- 创建 `.env.example` 模板文件

验收标准：
- `ruff check .` 无报错
- `pytest` 可运行（即使无测试用例）

---

### P1: 配置管理与异常体系

#### T1.1 实现 Pydantic Settings 配置

按设计文档 §3.1 实现完整配置类层次：

| 类名 | 基类 | 职责 |
|------|------|------|
| `DatabaseConfig` | `BaseModel` | 单个数据库连接配置 |
| `DeepSeekConfig` | `BaseModel` | DeepSeek LLM 配置 |
| `QueryConfig` | `BaseModel` | 查询执行配置 |
| `SchemaCacheConfig` | `BaseModel` | Schema 缓存配置 |
| `SecurityConfig` | `BaseModel` | 安全校验配置（白名单/黑名单） |
| `Settings` | `BaseSettings` | 顶层配置，聚合所有子配置 |

关键实现细节：
- 仅 `Settings` 继承 `BaseSettings`，嵌套类用 `BaseModel`（避免环境变量解析冲突）
- `Settings` 使用 `SettingsConfigDict(env_file=".env", env_nested_delimiter="__", extra="ignore")`
- `DatabaseConfig.password` 使用 `SecretStr` 类型
- `SecurityConfig.allowed_ast_nodes` 包含完整的白名单列表（设计文档 §3.1 中 30+ 节点类型）
- `Settings.default_database` 属性：优先返回 `is_default=True` 的配置，否则返回第一个

验收标准：
- 可从 `.env` 文件加载配置
- 可从环境变量加载配置（如 `DATABASES__0__HOST=localhost`）
- `SecretStr` 字段不会在 `repr()` 中泄露
- 缺少必填字段时抛出 `ValidationError`

#### T1.2 实现类型化异常体系

按设计文档 §3.3 实现异常层次：

```python
# pg_mcp/exceptions/errors.py
class ErrorCode(str, Enum):
    DB_NOT_FOUND = "DB_NOT_FOUND"
    SCHEMA_NOT_READY = "SCHEMA_NOT_READY"
    SQL_GENERATION_ERROR = "SQL_GENERATION_ERROR"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    QUERY_EXECUTION_ERROR = "QUERY_EXECUTION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"

class PgMcpError(Exception):
    """基础异常"""
    code: ErrorCode
    message: str
    details: dict | None

# 具体异常子类...
class DatabaseNotFoundError(PgMcpError): ...
class SchemaNotReadyError(PgMcpError): ...
class SQLGenerationError(PgMcpError): ...
class SecurityViolationError(PgMcpError): ...
class QueryTimeoutError(PgMcpError): ...
```

验收标准：
- 每个异常类携带 `ErrorCode` 枚举
- 异常可序列化为统一错误响应格式
- 单元测试覆盖所有异常类的构造和属性访问

#### T1.3 编写配置单元测试

```
tests/
├── conftest.py          # 共享 fixtures
├── test_config.py       # 配置加载测试
└── test_exceptions.py   # 异常体系测试
```

测试用例：
- 默认值加载
- 环境变量覆盖
- 必填字段缺失校验
- `SecretStr` 安全性
- `default_database` 属性逻辑
- 各异常类构造与 `ErrorCode` 映射

验收标准：
- `pytest tests/test_config.py tests/test_exceptions.py` 全部通过
- 覆盖率 ≥ 90%

---

### P2: SQL 安全校验器

#### T2.1 实现 SQLValidator 核心逻辑

按设计文档 §3.5 实现白名单模式的 SQL 安全校验器：

核心方法：

| 方法 | 职责 |
|------|------|
| `validate(sql) -> ValidationResult` | 主入口，协调所有检查 |
| `_check_top_level_statement(stmt)` | 检查顶层语句类型（仅允许 Select/With） |
| `_check_ast_nodes_whitelist(stmt)` | 遍历 AST，白名单校验所有节点类型 |
| `_check_blocked_functions(stmt)` | 检查危险函数调用（pg_sleep 等） |
| `_check_blocked_constructs(stmt)` | 检查危险构造（SELECT INTO、COPY 等） |
| `get_query_info(sql) -> dict` | 提取查询元信息（用于审计日志） |

关键实现细节：
- 使用 `sqlglot.parse(sql, dialect="postgres")` 解析
- `ValidationResult` 使用 `dataclass`，包含 `is_safe`、`message`、`detected_issues`
- 白名单节点集合从 `SecurityConfig.allowed_ast_nodes` 构建
- 对 `exp.Func` 和 `exp.Anonymous` 分别检查函数名
- SELECT INTO 需特殊处理：检查 `stmt.args.get("into")`
- 未知 AST 节点默认阻止（安全优先）

验收标准：
- 允许：简单 SELECT、JOIN、CTE、子查询 SELECT、聚合、UNION
- 阻止：INSERT、UPDATE、DELETE、DROP、TRUNCATE、CREATE、ALTER
- 阻止：pg_sleep、lo_export、pg_read_file 等危险函数
- 阻止：SELECT INTO、COPY
- 阻止：空 SQL、无效 SQL
- 阻止：子查询中嵌套写操作

#### T2.2 编写 SQL 校验器完整测试

按设计文档 §10.2 实现完整测试矩阵：

| 测试类别 | 用例数 | 覆盖场景 |
|----------|--------|----------|
| 允许的查询 | ≥ 5 | 简单 SELECT、WHERE、JOIN、CTE、复杂聚合 |
| 禁止的语句类型 | ≥ 5 | INSERT、UPDATE、DELETE、DROP、TRUNCATE |
| 禁止的构造 | ≥ 1 | SELECT INTO |
| 禁止的函数 | ≥ 3 | pg_sleep、lo_export、pg_read_file |
| 子查询安全 | ≥ 2 | 子查询 DELETE 阻止、子查询 SELECT 允许 |
| 边界情况 | ≥ 2 | 空 SQL、无效 SQL |

验收标准：
- `pytest tests/test_validator.py` 全部通过
- 覆盖率 ≥ 95%
- 无误报（合法 SELECT 不被阻止）
- 无漏报（危险操作全部拦截）

---

### P3: 数据库执行器

#### T3.1 实现 SQLExecutor 核心逻辑

按设计文档 §3.6 实现基于 asyncpg 的 SQL 执行器：

核心方法：

| 方法 | 职责 |
|------|------|
| `initialize(databases)` | 为每个数据库创建 asyncpg 连接池 |
| `get_pool(db_name) -> Pool` | 获取指定数据库的连接池 |
| `execute(db_name, sql, limit) -> QueryResult` | 执行 SQL 并返回结构化结果 |
| `_ensure_limit_via_ast(sql, limit) -> str` | 使用 SQLGlot AST 添加/修改 LIMIT |
| `health_check(db_name) -> bool` | 数据库健康检查 |
| `close()` | 关闭所有连接池 |

关键实现细节：
- 连接池使用 `server_settings={"default_transaction_read_only": "on"}` 强制只读
- 每次查询前设置 `SET statement_timeout = '{timeout}s'`
- LIMIT 处理采用 AST 方式：`sqlglot.parse_one(sql).limit(limit)`
- 截断检测：实际获取 `limit + 1` 行，若超出则标记 `truncated=True` 并只返回 `limit` 行
- AST 解析失败时回退到字符串拼接 `{sql} LIMIT {limit}`
- `QueryResult` 使用 Pydantic `BaseModel`，包含 `columns`、`rows`、`row_count`、`truncated`、`execution_time_ms`
- 执行时间使用 `datetime.now(timezone.utc)` 计算（毫秒精度）
- 捕获 `asyncpg.exceptions.QueryCanceledError` 转换为 `QueryTimeoutError`

验收标准：
- 连接池正确创建和关闭
- 只读事务强制生效（写操作抛异常）
- LIMIT AST 注入正确（无 LIMIT → 添加，已有 LIMIT → 取较小值）
- 超时机制生效
- 截断检测准确

#### T3.2 实现 QueryResult 数据模型

```python
class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list]
    row_count: int
    truncated: bool
    execution_time_ms: int
```

验收标准：
- 模型可正确序列化/反序列化
- `row_count` 与 `len(rows)` 一致

#### T3.3 编写数据库执行器测试

测试策略：使用 mock 替代真实数据库连接（单元测试），集成测试在 P9 阶段进行。

| 测试类别 | 用例 |
|----------|------|
| LIMIT AST 注入 | 无 LIMIT → 添加、已有小 LIMIT → 保持、已有大 LIMIT → 替换 |
| AST 回退 | 解析失败时字符串拼接 |
| 截断检测 | 恰好 limit 行（不截断）、limit+1 行（截断） |
| 超时处理 | `QueryCanceledError` → `QueryTimeoutError` |
| 连接池管理 | 初始化、获取、关闭 |

验收标准：
- `pytest tests/test_executor.py` 全部通过
- LIMIT 注入逻辑 100% 覆盖

---

### P4: Schema 发现服务

#### T4.1 实现 Schema 数据模型

按设计文档 §3.7 定义 Schema 相关的 Pydantic 模型：

```python
class ColumnInfo(BaseModel):
    name: str
    data_type: str
    nullable: bool
    is_primary_key: bool = False
    comment: str | None = None

class TableInfo(BaseModel):
    name: str
    schema_name: str
    columns: list[ColumnInfo]
    comment: str | None = None

class SchemaInfo(BaseModel):
    database: str
    tables: list[TableInfo]
    cached_at: datetime
```

验收标准：
- 模型可正确构造和序列化
- `cached_at` 使用 UTC 时区

#### T4.2 实现 SchemaService 核心逻辑

核心方法：

| 方法 | 职责 |
|------|------|
| `discover(db_name, pool) -> SchemaInfo` | 批量查询 Schema 信息 |
| `get_schema(db_name, pool?) -> SchemaInfo` | 获取缓存的 Schema（带 TTL 检查） |
| `is_cache_expired(db_name) -> bool` | 检查缓存是否过期 |
| `invalidate_cache(db_name?)` | 使缓存失效 |
| `format_for_llm(schema_info) -> str` | 格式化 Schema 供 LLM 使用 |

关键实现细节：
- **批量查询**（解决 N+1）：使用单条 SQL 通过 CTE 联合 `information_schema.tables`、`information_schema.columns`、`pg_indexes`、`pg_description` 获取所有表和列信息
- 排除系统 schema：`pg_catalog`、`information_schema`、`pg_toast`
- 主键检测：通过 `table_constraints` + `key_column_usage` 关联查询
- **TTL 缓存**：`SchemaCacheConfig.ttl_minutes` 控制过期时间
- **自动刷新**：过期时若 `auto_refresh=True` 且有 pool，自动重新发现
- 过期但无法刷新时返回过期缓存（降级策略）
- `format_for_llm` 输出格式：`表: schema.table_name -- comment\n  - col: type [PK] NOT NULL -- comment`

验收标准：
- 批量查询正确获取表、列、主键、注释
- 缓存 TTL 机制正确
- 自动刷新在过期时触发
- `format_for_llm` 输出可读且包含完整信息
- 系统 schema 被正确排除

#### T4.3 编写 Schema 服务测试

| 测试类别 | 用例 |
|----------|------|
| 数据模型 | ColumnInfo、TableInfo、SchemaInfo 构造 |
| 缓存逻辑 | 未缓存返回 None、缓存命中、缓存过期 |
| 自动刷新 | 过期 + auto_refresh=True → 重新发现 |
| LLM 格式化 | 输出包含表名、列名、类型、PK 标记、注释 |
| 缓存失效 | 单库失效、全部失效 |

验收标准：
- `pytest tests/test_schema.py` 全部通过

---

### P5: 数据模型层

#### T5.1 实现请求模型

按设计文档 §4.1 实现：

```python
# pg_mcp/models/request.py
ReturnMode = Literal["sql", "result", "both"]

class QueryRequest(BaseModel):
    query: str = Field(..., description="自然语言查询描述")
    database: str | None = Field(None, description="目标数据库名称")
    return_mode: ReturnMode = Field("both", description="返回模式")
    limit: int = Field(100, ge=1, le=1000, description="结果行数限制")
```

#### T5.2 实现响应模型

按设计文档 §4.1 实现完整响应模型层次：

| 模型 | 职责 |
|------|------|
| `QueryResultData` | 查询结果数据（columns, rows, row_count, truncated） |
| `ValidationInfo` | 验证信息（status, confidence, message） |
| `QueryMetadata` | 查询元数据（database, execution_time_ms, generated_at） |
| `QueryResponseData` | 查询响应数据（sql, result, validation, metadata） |
| `QueryResponse` | 成功响应（success=True, data, request_id） |
| `ErrorResponse` | 错误响应（success=False, code, message, details） |

关键实现细节：
- `QueryResponse.request_id` 使用 `uuid.uuid4()` 自动生成
- `ErrorResponse.timestamp` 使用 `datetime.now(timezone.utc)`
- `ErrorResponse.model_dump()` 自定义序列化：将 code/message/details 嵌套在 `error` 字段下

验收标准：
- 所有模型可正确构造和序列化
- `ErrorResponse.model_dump()` 输出符合统一错误格式
- `request_id` 自动生成且唯一

#### T5.3 编写数据模型测试

验收标准：
- 请求模型字段验证（limit 范围、return_mode 枚举）
- 响应模型序列化格式正确
- ErrorResponse 自定义 model_dump 输出正确

---

### P6: LLM 服务（DeepSeek 集成）

#### T6.1 实现 LLMService 核心逻辑

按设计文档 §3.8 实现 DeepSeek API 集成：

核心方法：

| 方法 | 职责 |
|------|------|
| `generate_sql(natural_query, schema_info, dialect) -> str` | 自然语言转 SQL 主入口 |
| `_call_api_with_retry(user_message) -> str` | 带指数退避重试的 API 调用 |
| `_exponential_backoff(attempt)` | 指数退避延迟（含 ±25% 抖动） |
| `_clean_sql_response(response) -> str` | 清理 LLM 响应，提取纯 SQL |
| `close()` | 关闭 httpx 客户端 |

关键实现细节：

**System Prompt 设计**：
```
你是一个 PostgreSQL SQL 专家。根据用户的自然语言描述和数据库 Schema 信息，生成对应的 SQL 查询语句。
规则：
1. 只生成 SELECT 查询语句，禁止任何数据修改操作
2. 使用标准 PostgreSQL 语法
3. 只返回 SQL 语句，不要包含任何解释或 markdown 格式
4. 如果用户请求涉及数据修改，返回 "ERROR: 仅支持查询操作"
5. 合理使用 JOIN、GROUP BY、ORDER BY 等子句
6. 对于模糊的查询，做出合理的假设并生成 SQL
```

**User Message 构建**：
```
数据库 Schema 信息：
{schema_text}  ← SchemaService.format_for_llm() 输出

用户查询：{natural_query}

请生成对应的 SQL 查询语句：
```

**指数退避重试**：
- 重试条件：HTTP 429（Rate Limit）、5xx 错误、超时
- 退避公式：`base_delay * 2^attempt ± 25% jitter`
- 最大重试次数：`config.max_retries`（默认 3）
- 非重试错误（4xx 非 429）直接抛出 `SQLGenerationError`

**响应清理**：
- 移除 markdown 代码块标记（` ```sql ` 和 ` ``` `）
- 去除首尾空白
- 处理 LLM 返回 "ERROR:" 前缀的拒绝响应

**httpx 客户端配置**：
- `base_url`: DeepSeek API 地址
- `timeout`: 配置的超时秒数
- `headers`: Bearer token 认证

验收标准：
- API 调用成功时返回清理后的 SQL
- 429/5xx 错误触发重试（最多 max_retries 次）
- 指数退避延迟正确（含抖动）
- 超时触发重试
- 所有重试失败后抛出 `SQLGenerationError`
- markdown 代码块正确清理
- httpx 客户端正确关闭

#### T6.2 编写 LLM 服务测试

使用 `httpx` mock 或 `respx` 库模拟 DeepSeek API 响应：

| 测试类别 | 用例 |
|----------|------|
| 正常调用 | 返回纯 SQL → 正确解析 |
| markdown 清理 | 返回 ` ```sql SELECT... ``` ` → 提取纯 SQL |
| 重试机制 | 第 1 次 429 → 第 2 次成功 |
| 重试耗尽 | 3 次全部 500 → 抛出 SQLGenerationError |
| 非重试错误 | 401 → 直接抛出 SQLGenerationError |
| 超时重试 | TimeoutException → 重试 |
| 客户端关闭 | close() 正确调用 aclose() |

验收标准：
- `pytest tests/test_llm.py` 全部通过
- 重试逻辑 100% 覆盖

---

### P7: 应用上下文与生命周期管理

#### T7.1 实现 AppContext 依赖注入容器

按设计文档 §3.2 实现：

```python
@dataclass
class AppContext:
    settings: Settings
    validator: SQLValidator
    executor: SQLExecutor
    schema_service: SchemaService
    llm_service: LLMService

    async def close(self):
        await self.llm_service.close()
        await self.executor.close()

_context: AppContext | None = None

def get_context() -> AppContext:
    if _context is None:
        raise RuntimeError("AppContext 未初始化")
    return _context

def set_context(ctx: AppContext):
    global _context
    _context = ctx
```

验收标准：
- `get_context()` 在未初始化时抛出 `RuntimeError`
- `set_context()` 正确设置全局上下文
- `close()` 依次关闭 LLM 服务和执行器

#### T7.2 实现 lifespan 生命周期管理

按设计文档 §5.1 实现 `__main__.py` 中的 lifespan：

启动时序（严格按顺序）：
1. 加载 `Settings` 配置
2. 初始化 `SQLValidator`（传入 `settings.security`）
3. 初始化 `SQLExecutor`（传入 `settings.query`），调用 `executor.initialize(settings.databases)` 创建连接池
4. 初始化 `SchemaService`（传入 `settings.schema_cache`），遍历所有数据库调用 `discover()`
5. 初始化 `LLMService`（传入 `settings.deepseek` 和 `schema_service`）
6. 创建 `AppContext` 并调用 `set_context()`

关闭时序：
- `finally` 块中依次关闭 `llm_service` 和 `executor`
- 即使启动失败也确保已创建的资源被清理

关键实现细节：
- 使用 `@asynccontextmanager` 装饰器
- `executor` 和 `llm_service` 在 try 外声明为 `None`，在 finally 中检查后关闭
- 将 lifespan 赋值给 `mcp.lifespan`
- 启动/关闭时打印状态信息

验收标准：
- 正常启动：所有服务按序初始化，打印就绪信息
- 启动失败：已创建的资源被正确清理
- 正常关闭：所有资源被释放

#### T7.3 编写生命周期测试

| 测试类别 | 用例 |
|----------|------|
| AppContext | 构造、get/set、close |
| lifespan 正常 | 启动 → yield → 关闭 |
| lifespan 失败 | 中途异常 → 已创建资源被清理 |

验收标准：
- `pytest tests/test_context.py tests/test_lifespan.py` 全部通过

---

### P8: FastMCP Tool 注册

#### T8.1 实现 query_database Tool

按设计文档 §3.4 实现核心 Tool：

```python
@mcp.tool()
async def query_database(
    query: str,
    database: str | None = None,
    return_mode: ReturnMode = "both",
    limit: int = 100
) -> dict:
```

处理流程（严格按顺序）：
1. 验证 `return_mode` 合法性
2. 确定目标数据库（参数指定 > 默认数据库）
3. 获取数据库配置，不存在则抛出 `DatabaseNotFoundError`
4. 获取 Schema 信息（带缓存），不存在则抛出 `SchemaNotReadyError`
5. 调用 `LLMService.generate_sql()` 生成 SQL
6. 调用 `SQLValidator.validate()` 校验安全性，不通过则返回 `ErrorResponse`
7. 根据 `return_mode` 决定是否执行：
   - `"sql"`: 只返回 SQL
   - `"result"`: 只返回执行结果
   - `"both"`: 返回 SQL + 执行结果
8. `limit` 取 `min(limit, settings.query.max_rows_limit)` 防止超限

异常处理：
- `PgMcpError` → 结构化 `ErrorResponse`（暴露错误码和消息）
- `Exception` → 通用 `ErrorResponse`（不暴露内部细节，消息为"查询执行过程中发生错误，请稍后重试"）

辅助函数：
```python
def _get_database_config(ctx, db_name: str):
    for db in ctx.settings.databases:
        if db.name == db_name:
            return db
    return None
```

验收标准：
- 完整流程：自然语言 → SQL 生成 → 安全校验 → 执行 → 返回结果
- 三种 return_mode 正确处理
- 数据库不存在 → `DB_NOT_FOUND` 错误
- Schema 未就绪 → `SCHEMA_NOT_READY` 错误
- SQL 校验失败 → `SECURITY_VIOLATION` 错误
- 未预期异常 → 通用错误（不泄露内部信息）

#### T8.2 编写 Tool 集成测试

使用 mock 替代外部依赖（LLM API、数据库），测试 Tool 的完整处理流程：

| 测试类别 | 用例 |
|----------|------|
| 正常流程 | 自然语言 → SQL → 校验通过 → 执行 → 返回 |
| return_mode=sql | 只返回 SQL，不执行 |
| return_mode=result | 只返回结果，不含 SQL |
| 数据库不存在 | → DB_NOT_FOUND |
| Schema 未就绪 | → SCHEMA_NOT_READY |
| SQL 校验失败 | → SECURITY_VIOLATION |
| LLM 调用失败 | → SQL_GENERATION_ERROR |
| 执行超时 | → QUERY_TIMEOUT |
| 未预期异常 | → 通用错误 |

验收标准：
- `pytest tests/test_tool.py` 全部通过
- 所有错误路径覆盖

---

### P9: 集成测试与端到端验证

#### T9.1 搭建集成测试环境

- 创建 `docker-compose.test.yml`，包含 PostgreSQL 测试实例
- 创建测试数据库初始化脚本（建表、插入测试数据）
- 配置 `.env.test` 测试环境变量

```yaml
# docker-compose.test.yml
services:
  postgres-test:
    image: postgres:16
    environment:
      POSTGRES_DB: test_db
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_pass
    ports:
      - "5433:5432"
    volumes:
      - ./tests/fixtures/init.sql:/docker-entrypoint-initdb.d/init.sql
```

验收标准：
- `docker compose -f docker-compose.test.yml up -d` 启动测试数据库
- 测试数据库包含至少 2 张表、有外键关系、有注释

#### T9.2 编写端到端集成测试

使用真实 PostgreSQL（Docker）+ mock LLM API 进行端到端测试：

| 测试场景 | 验证点 |
|----------|--------|
| Schema 发现 | 正确获取表、列、主键、注释 |
| SQL 执行 | 只读查询成功，写操作被拒绝 |
| LIMIT 注入 | AST 方式正确添加 LIMIT |
| 截断检测 | 大结果集正确截断 |
| 超时处理 | 慢查询被超时中断 |
| 完整流程 | NL → SQL → 校验 → 执行 → 响应 |

验收标准：
- `pytest tests/integration/` 全部通过（需 Docker 环境）
- 端到端流程无阻塞

#### T9.3 创建 Docker 部署配置

按设计文档 §11.2 创建生产 Dockerfile：

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "pg_mcp"]
```

验收标准：
- `docker build -t pg-mcp .` 成功构建
- `docker run pg-mcp` 可启动（需配置环境变量）

#### T9.4 创建 Claude Desktop 配置示例

按设计文档 §8.3 创建配置示例文件：

```json
{
  "mcpServers": {
    "pg-mcp": {
      "command": "python",
      "args": ["-m", "pg_mcp"],
      "env": {
        "DB_PASSWORD": "your_password",
        "DEEPSEEK_API_KEY": "sk-xxx"
      }
    }
  }
}
```

验收标准：
- 配置文件语法正确
- 文档说明清晰

---

## 4. 任务依赖关系图

```
T0.1 ─┬─ T0.2 ─── T0.3 ─── T0.4
       │
       ▼
T1.1 ─┬─ T1.2 ─── T1.3
       │
       ├──────────────────────────────┐
       ▼                              ▼
T2.1 ─── T2.2                  T3.1 ─── T3.2 ─── T3.3
       │                              │
       │                              ▼
       │                        T4.1 ─── T4.2 ─── T4.3
       │                              │
       │         T5.1 ─── T5.2 ─── T5.3
       │              │           │
       │              ▼           ▼
       │        T6.1 ─── T6.2
       │              │
       ▼              ▼
T7.1 ─── T7.2 ─── T7.3
       │
       ▼
T8.1 ─── T8.2
       │
       ▼
T9.1 ─── T9.2 ─── T9.3 ─── T9.4
```

关键路径：T0 → T1 → T3 → T4 → T6 → T7 → T8 → T9

可并行的任务组：
- T2（SQL 校验器）与 T3（数据库执行器）可并行
- T5（数据模型）与 T3/T4 可并行
- T9.3（Docker）与 T9.4（配置示例）可并行

---

## 5. 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| SQLGlot 白名单遗漏合法 AST 节点 | 合法查询被误拦截 | 中 | 充分测试 + 配置化白名单，可动态扩展 |
| DeepSeek API 不稳定 | SQL 生成失败 | 中 | 指数退避重试 + 错误降级 |
| asyncpg 连接池耗尽 | 查询阻塞 | 低 | 合理配置 min/max_connections + 超时 |
| FastMCP 版本兼容性 | API 变更导致适配问题 | 低 | 锁定最低版本 + CI 测试 |
| Schema 发现遗漏特殊对象 | LLM 生成 SQL 引用不存在的表 | 低 | 批量查询覆盖 BASE TABLE，后续可扩展 VIEW |
| LLM 生成的 SQL 绕过校验器 | 安全风险 | 低 | 白名单模式 + 数据库只读角色双重防护 |

---

## 6. 验收检查清单

### 6.1 功能验收

- [ ] `python -m pg_mcp` 可正常启动
- [ ] 配置从 `.env` / 环境变量正确加载
- [ ] Schema 自动发现并缓存
- [ ] 自然语言查询 → SQL 生成 → 安全校验 → 执行 → 返回结果
- [ ] 三种 return_mode 正确工作
- [ ] 只读限制生效（写操作被拦截）
- [ ] 危险函数被拦截
- [ ] 查询超时机制生效
- [ ] 结果截断机制生效
- [ ] 错误响应格式统一

### 6.2 安全验收

- [ ] INSERT/UPDATE/DELETE/DROP 等写操作被 SQLValidator 拦截
- [ ] pg_sleep、lo_export 等危险函数被拦截
- [ ] SELECT INTO、COPY 等危险构造被拦截
- [ ] 子查询中的写操作被拦截
- [ ] 数据库连接强制只读事务
- [ ] 密码等敏感信息不在日志中泄露
- [ ] 未预期异常不暴露内部实现细节

### 6.3 质量验收

- [ ] 单元测试覆盖率 ≥ 85%
- [ ] `ruff check .` 无报错
- [ ] 所有 Pydantic 模型类型安全
- [ ] 异步资源正确关闭（无泄漏）
- [ ] Docker 镜像可正常构建和运行

---

## 7. PRD 需求追溯矩阵

| PRD 需求 | 实现任务 | 验证方式 |
|----------|----------|----------|
| FR-001 数据库连接配置 | T1.1 (Settings) | T1.3 单元测试 |
| FR-002 Schema 自动发现 | T4.2 (SchemaService) | T4.3 + T9.2 集成测试 |
| FR-004 自然语言输入解析 | T8.1 (query_database 参数) | T8.2 Tool 测试 |
| FR-005 SQL 生成 | T6.1 (LLMService) | T6.2 + T9.2 |
| FR-006 SQL 安全校验 | T2.1 (SQLValidator) | T2.2 完整测试矩阵 |
| FR-007 SQL 执行 | T3.1 (SQLExecutor) | T3.3 + T9.2 |
| FR-009 MCP Tools | T8.1 (FastMCP Tool) | T8.2 + T9.2 |
| NFR-001 响应时间 | T3.1 (超时配置) | T9.2 集成测试 |
| NFR-003 数据安全 | T1.1 (SecretStr) | T1.3 |
| NFR-004 查询安全 | T2.1 + T3.1 (只读) | T2.2 + T9.2 |
| NFR-006 错误处理 | T1.2 + T8.1 | T8.2 |

---

## 8. 附录

### 8.1 修订历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0.0 | 2026-02-23 | 初始版本 |
