# PostgreSQL MCP Server 技术设计文档

> 版本: 1.1.0
> 创建日期: 2026-02-23
> 更新日期: 2026-02-23
> 状态: 草稿
> 关联 PRD: [0001-pg-mcp-prd.md](./0001-pg-mcp-prd.md)

---

## 1. 概述

### 1.1 设计目标

基于 PRD 需求，使用以下技术栈构建 PostgreSQL MCP Server：

| 组件 | 技术选型 | 用途 |
|------|----------|------|
| MCP 框架 | FastMCP | 简化 MCP Server 开发，装饰器定义 Tools |
| 数据库驱动 | asyncpg | 高性能异步 PostgreSQL 连接池 |
| SQL 解析 | SQLGlot | SQL AST 解析与安全校验 |
| 配置管理 | Pydantic | 类型安全的配置验证与环境变量支持 |
| LLM 集成 | DeepSeek API | 自然语言转 SQL |

### 1.2 设计原则

1. **异步优先**：全链路异步，充分利用 asyncpg 和 httpx 的异步能力
2. **类型安全**：Pydantic 模型贯穿配置、请求、响应
3. **安全纵深**：SQLGlot AST 白名单校验 + 数据库只读角色双重防护
4. **关注点分离**：清晰的模块边界，便于测试和维护
5. **依赖注入**：通过 AppContext 容器管理服务依赖，提高可测试性

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              MCP Client                                  │
│                    (Claude Desktop / IDE Plugin)                         │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ MCP Protocol (stdio/SSE)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           FastMCP Server                                 │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                        Tool: query_database                        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
┌───────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  LLM Service  │       │  SQL Validator  │       │   DB Executor   │
│   (DeepSeek)  │       │   (SQLGlot)     │       │   (asyncpg)     │
└───────────────┘       └─────────────────┘       └─────────────────┘
        │                                                   │
        ▼                                                   ▼
┌───────────────┐                                 ┌─────────────────┐
│ DeepSeek API  │                                 │   PostgreSQL    │
└───────────────┘                                 └─────────────────┘
```

### 2.2 模块划分

```
pg_mcp/
├── __init__.py
├── __main__.py              # 入口点
├── server.py                # FastMCP Server 定义
├── context.py               # 应用上下文（依赖注入容器）
├── config/
│   ├── __init__.py
│   └── settings.py          # Pydantic Settings 配置
├── services/
│   ├── __init__.py
│   ├── llm.py               # DeepSeek LLM 服务
│   ├── schema.py            # Schema 发现与缓存
│   └── executor.py          # SQL 执行器
├── security/
│   ├── __init__.py
│   └── validator.py         # SQLGlot SQL 安全校验（白名单模式）
├── models/
│   ├── __init__.py
│   ├── schema.py            # Schema 数据模型
│   ├── request.py           # 请求模型
│   └── response.py          # 响应模型
├── exceptions/
│   ├── __init__.py
│   └── errors.py            # 类型化异常定义
└── utils/
    ├── __init__.py
    └── logging.py           # 日志工具
```

---

## 3. 核心模块设计

### 3.1 配置管理 (Pydantic Settings)

使用 `pydantic-settings` 实现类型安全的配置管理，支持环境变量和配置文件。

> **注意**：仅顶层 `Settings` 类继承 `BaseSettings`，嵌套配置类使用 `BaseModel` 以避免环境变量解析冲突。

```python
# pg_mcp/config/settings.py
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class DatabaseConfig(BaseModel):
    """单个数据库连接配置"""
    name: str
    host: str = "localhost"
    port: int = 5432
    database: str
    username: str
    password: SecretStr
    ssl_mode: str = "prefer"
    min_connections: int = 1
    max_connections: int = 10
    is_default: bool = False

class DeepSeekConfig(BaseModel):
    """DeepSeek LLM 配置"""
    api_key: SecretStr
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    temperature: float = 0.1
    max_tokens: int = 2000
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_base_delay: float = 1.0  # 指数退避基础延迟（秒）

class QueryConfig(BaseModel):
    """查询执行配置"""
    timeout_seconds: int = 30
    max_rows: int = 100
    max_rows_limit: int = 1000
    default_return_mode: str = "both"  # sql | result | both

class SchemaCacheConfig(BaseModel):
    """Schema 缓存配置"""
    ttl_minutes: int = 60  # 缓存过期时间
    auto_refresh: bool = True  # 是否自动刷新过期缓存

class SecurityConfig(BaseModel):
    """安全配置"""
    # 白名单模式：仅允许以下语句类型
    allowed_statement_types: list[str] = ["Select"]
    # 白名单模式：允许的 AST 节点类型
    allowed_ast_nodes: list[str] = [
        "Select", "From", "Join", "Where", "Group", "Having",
        "Order", "Limit", "Offset", "With", "Union", "Intersect",
        "Except", "Subquery", "Column", "Table", "Alias", "Star",
        "Literal", "Func", "Case", "Cast", "Between", "In", "Like",
        "And", "Or", "Not", "Eq", "NEq", "GT", "GTE", "LT", "LTE",
        "Add", "Sub", "Mul", "Div", "Mod", "Neg", "Paren",
        "Distinct", "All", "Null", "Boolean", "Interval",
        "Extract", "Coalesce", "NullIf", "Greatest", "Least",
    ]
    # 黑名单：危险函数（在白名单基础上额外拦截）
    blocked_functions: list[str] = [
        "pg_sleep", "lo_export", "lo_import",
        "pg_read_file", "pg_write_file", "pg_read_binary_file",
        "pg_ls_dir", "pg_stat_file", "pg_terminate_backend",
        "pg_cancel_backend", "pg_reload_conf", "set_config",
        "current_setting",  # 可能泄露配置信息
    ]
    # 黑名单：危险语句类型（SELECT INTO, COPY 等）
    blocked_constructs: list[str] = [
        "Into",  # SELECT INTO
        "Copy",  # COPY
        "Lock",  # LOCK TABLE
    ]
    enable_prompt_injection_check: bool = True

class Settings(BaseSettings):
    """主配置类"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore"
    )

    server_name: str = "pg-mcp-server"
    log_level: str = "INFO"
    databases: list[DatabaseConfig] = []
    deepseek: DeepSeekConfig
    query: QueryConfig = QueryConfig()
    security: SecurityConfig = SecurityConfig()
    schema_cache: SchemaCacheConfig = SchemaCacheConfig()

    @property
    def default_database(self) -> DatabaseConfig | None:
        """获取默认数据库配置"""
        for db in self.databases:
            if db.is_default:
                return db
        return self.databases[0] if self.databases else None
```

### 3.2 应用上下文（依赖注入）

使用 `AppContext` 容器管理服务依赖，替代全局单例模式，提高可测试性。

```python
# pg_mcp/context.py
from dataclasses import dataclass
from pg_mcp.config.settings import Settings
from pg_mcp.services.llm import LLMService
from pg_mcp.services.executor import SQLExecutor
from pg_mcp.services.schema import SchemaService
from pg_mcp.security.validator import SQLValidator

@dataclass
class AppContext:
    """应用上下文 - 依赖注入容器"""
    settings: Settings
    validator: SQLValidator
    executor: SQLExecutor
    schema_service: SchemaService
    llm_service: LLMService

    async def close(self):
        """关闭所有资源"""
        await self.llm_service.close()
        await self.executor.close()

# 全局上下文（在 lifespan 中初始化）
_context: AppContext | None = None

def get_context() -> AppContext:
    """获取应用上下文"""
    if _context is None:
        raise RuntimeError("应用上下文未初始化")
    return _context

def set_context(ctx: AppContext) -> None:
    """设置应用上下文"""
    global _context
    _context = ctx
```

### 3.3 类型化异常定义

定义类型化异常，实现精确的错误处理和映射。

```python
# pg_mcp/exceptions/errors.py
from enum import Enum

class ErrorCode(str, Enum):
    """错误码枚举"""
    DB_NOT_FOUND = "DB_NOT_FOUND"
    DB_CONNECTION_ERROR = "DB_CONNECTION_ERROR"
    SCHEMA_NOT_READY = "SCHEMA_NOT_READY"
    SQL_GENERATION_ERROR = "SQL_GENERATION_ERROR"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    QUERY_EXECUTION_ERROR = "QUERY_EXECUTION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

class PgMcpError(Exception):
    """基础异常类"""
    def __init__(self, code: ErrorCode, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

class DatabaseNotFoundError(PgMcpError):
    def __init__(self, db_name: str):
        super().__init__(
            ErrorCode.DB_NOT_FOUND,
            f"数据库 '{db_name}' 未配置",
            {"database": db_name}
        )

class SchemaNotReadyError(PgMcpError):
    def __init__(self, db_name: str):
        super().__init__(
            ErrorCode.SCHEMA_NOT_READY,
            f"数据库 '{db_name}' 的 Schema 缓存未就绪",
            {"database": db_name}
        )

class SecurityViolationError(PgMcpError):
    def __init__(self, message: str, detected_issues: list[str]):
        super().__init__(
            ErrorCode.SECURITY_VIOLATION,
            message,
            {"detected_issues": detected_issues}
        )

class QueryTimeoutError(PgMcpError):
    def __init__(self, timeout_seconds: int):
        super().__init__(
            ErrorCode.QUERY_TIMEOUT,
            f"查询执行超时（{timeout_seconds}秒）",
            {"timeout_seconds": timeout_seconds}
        )

class SQLGenerationError(PgMcpError):
    def __init__(self, message: str):
        super().__init__(
            ErrorCode.SQL_GENERATION_ERROR,
            f"SQL 生成失败: {message}"
        )
```

### 3.4 FastMCP Server 定义

使用 FastMCP 装饰器定义 MCP Tool，通过依赖注入获取服务实例。

```python
# pg_mcp/server.py
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Literal
from pg_mcp.context import get_context
from pg_mcp.models.response import QueryResponse, ErrorResponse
from pg_mcp.exceptions.errors import (
    PgMcpError, DatabaseNotFoundError, SchemaNotReadyError
)

# 初始化 FastMCP Server
mcp = FastMCP("pg-mcp-server")

# 返回模式类型
ReturnMode = Literal["sql", "result", "both"]


class QueryInput(BaseModel):
    """query_database 工具输入参数"""
    query: str = Field(..., description="自然语言查询描述")
    database: str | None = Field(None, description="目标数据库名称")
    return_mode: ReturnMode = Field("both", description="返回模式")
    limit: int = Field(100, ge=1, le=1000, description="结果行数限制")


@mcp.tool()
async def query_database(
    query: str,
    database: str | None = None,
    return_mode: ReturnMode = "both",
    limit: int = 100
) -> dict:
    """
    通过自然语言查询 PostgreSQL 数据库。

    将自然语言描述转换为 SQL 查询并执行，返回查询结果。
    仅支持 SELECT 查询，禁止任何数据修改操作。

    Args:
        query: 自然语言查询描述，如 "查询所有用户的姓名和邮箱"
        database: 目标数据库名称，不指定则使用默认数据库
        return_mode: 返回模式 - "sql"(仅SQL), "result"(仅结果), "both"(两者)
        limit: 结果行数限制，默认100，最大1000

    Returns:
        包含 SQL 语句和/或查询结果的字典
    """
    ctx = get_context()

    try:
        # 1. 验证 return_mode（类型系统已保证，此处为防御性检查）
        if return_mode not in ("sql", "result", "both"):
            return ErrorResponse(
                code="INVALID_INPUT",
                message=f"无效的 return_mode: {return_mode}"
            ).model_dump()

        # 2. 确定目标数据库
        db_name = database or (ctx.settings.default_database.name if ctx.settings.default_database else None)
        if not db_name:
            raise DatabaseNotFoundError(database or "default")

        db_config = _get_database_config(ctx, db_name)
        if not db_config:
            raise DatabaseNotFoundError(db_name)

        # 3. 获取 Schema 信息（带缓存检查）
        schema_info = await ctx.schema_service.get_schema(db_config.name)
        if schema_info is None:
            raise SchemaNotReadyError(db_config.name)

        # 4. 调用 LLM 生成 SQL
        generated_sql = await ctx.llm_service.generate_sql(
            natural_query=query,
            schema_info=schema_info,
            dialect="postgres"
        )

        # 5. SQL 安全校验（白名单模式）
        validation_result = ctx.validator.validate(generated_sql)
        if not validation_result.is_safe:
            return ErrorResponse(
                code="SECURITY_VIOLATION",
                message=validation_result.message,
                details={"detected": validation_result.detected_issues}
            ).model_dump()

        # 6. 根据 return_mode 决定是否执行
        response_data = {"sql": generated_sql}

        if return_mode in ("result", "both"):
            # 执行 SQL
            result = await ctx.executor.execute(
                db_name=db_config.name,
                sql=generated_sql,
                limit=min(limit, ctx.settings.query.max_rows_limit)
            )
            response_data["result"] = result.model_dump()

        if return_mode == "result":
            del response_data["sql"]

        return QueryResponse(
            success=True,
            data=response_data
        ).model_dump()

    except PgMcpError as e:
        # 类型化异常 -> 结构化错误响应
        return ErrorResponse(
            code=e.code.value,
            message=e.message,
            details=e.details
        ).model_dump()
    except Exception as e:
        # 未预期异常 -> 通用错误（不暴露内部细节）
        return ErrorResponse(
            code="QUERY_EXECUTION_ERROR",
            message="查询执行过程中发生错误，请稍后重试"
        ).model_dump()


def _get_database_config(ctx, db_name: str):
    """获取数据库配置"""
    for db in ctx.settings.databases:
        if db.name == db_name:
            return db
    return None
```

### 3.5 SQL 安全校验器 (SQLGlot) - 白名单模式

使用 SQLGlot 解析 SQL AST，采用**白名单模式**进行安全校验，仅允许明确列出的 AST 节点类型。

> **重要**：白名单模式比黑名单更安全，可防止遗漏危险构造（如 SELECT INTO、COPY 等）。

```python
# pg_mcp/security/validator.py
import sqlglot
from sqlglot import exp
from dataclasses import dataclass, field
from pg_mcp.config.settings import SecurityConfig

@dataclass
class ValidationResult:
    """校验结果"""
    is_safe: bool
    message: str = ""
    detected_issues: list[str] = field(default_factory=list)


class SQLValidator:
    """SQL 安全校验器 - 基于 SQLGlot AST 白名单分析"""

    def __init__(self, config: SecurityConfig):
        self.config = config
        # 构建允许的 AST 节点类型集合
        self.allowed_nodes = set(config.allowed_ast_nodes)
        # 构建阻止的函数集合（小写）
        self.blocked_functions = set(f.lower() for f in config.blocked_functions)
        # 构建阻止的构造集合
        self.blocked_constructs = set(config.blocked_constructs)

    def validate(self, sql: str) -> ValidationResult:
        """
        校验 SQL 语句安全性（白名单模式）

        Args:
            sql: 待校验的 SQL 语句

        Returns:
            ValidationResult: 校验结果
        """
        try:
            # 解析 SQL（使用 PostgreSQL 方言）
            statements = sqlglot.parse(sql, dialect="postgres")
        except Exception as e:
            return ValidationResult(
                is_safe=False,
                message=f"SQL 语法解析失败: {str(e)}"
            )

        if not statements:
            return ValidationResult(
                is_safe=False,
                message="SQL 语句为空"
            )

        issues = []

        for stmt in statements:
            # 1. 检查顶层语句类型（必须是 SELECT 或 WITH）
            stmt_issues = self._check_top_level_statement(stmt)
            issues.extend(stmt_issues)

            # 2. 白名单检查：遍历所有 AST 节点
            node_issues = self._check_ast_nodes_whitelist(stmt)
            issues.extend(node_issues)

            # 3. 黑名单检查：危险函数
            func_issues = self._check_blocked_functions(stmt)
            issues.extend(func_issues)

            # 4. 黑名单检查：危险构造（SELECT INTO 等）
            construct_issues = self._check_blocked_constructs(stmt)
            issues.extend(construct_issues)

        if issues:
            return ValidationResult(
                is_safe=False,
                message="检测到非只读操作，本服务仅支持 SELECT 查询",
                detected_issues=issues
            )

        return ValidationResult(is_safe=True, message="校验通过")

    def _check_top_level_statement(self, stmt: exp.Expression) -> list[str]:
        """检查顶层语句类型"""
        issues = []
        stmt_type = stmt.__class__.__name__

        # 允许 Select 和 With (CTE)
        if stmt_type == "Select":
            return issues
        elif stmt_type == "With":
            # CTE 的主体必须是 SELECT
            if not isinstance(stmt.this, exp.Select):
                issues.append(f"WITH 语句的主体必须是 SELECT，实际为: {stmt.this.__class__.__name__}")
        else:
            issues.append(f"禁止的顶层语句类型: {stmt_type}")

        return issues

    def _check_ast_nodes_whitelist(self, stmt: exp.Expression) -> list[str]:
        """白名单检查：遍历所有 AST 节点"""
        issues = []

        for node in stmt.walk():
            node_type = node.__class__.__name__
            if node_type not in self.allowed_nodes:
                # 检查是否是已知的危险类型
                if node_type in ("Insert", "Update", "Delete", "Drop", "Create",
                                 "Alter", "Truncate", "Grant", "Revoke", "Copy"):
                    issues.append(f"禁止的语句类型: {node_type}")
                elif node_type not in self.blocked_constructs:
                    # 未知节点类型，记录但不一定阻止（可配置）
                    # 为安全起见，默认阻止未知节点
                    issues.append(f"不允许的 AST 节点类型: {node_type}")

        return issues

    def _check_blocked_functions(self, stmt: exp.Expression) -> list[str]:
        """检查是否调用了危险函数"""
        issues = []

        for func in stmt.find_all(exp.Func):
            func_name = getattr(func, 'name', '').lower()
            if func_name in self.blocked_functions:
                issues.append(f"禁止的函数调用: {func_name}")

        # 检查匿名函数调用
        for anon in stmt.find_all(exp.Anonymous):
            func_name = anon.this.lower() if isinstance(anon.this, str) else ""
            if func_name in self.blocked_functions:
                issues.append(f"禁止的函数调用: {func_name}")

        return issues

    def _check_blocked_constructs(self, stmt: exp.Expression) -> list[str]:
        """检查危险构造（SELECT INTO 等）"""
        issues = []

        for node in stmt.walk():
            node_type = node.__class__.__name__
            if node_type in self.blocked_constructs:
                issues.append(f"禁止的构造: {node_type}")

        # 特别检查 SELECT INTO
        if isinstance(stmt, exp.Select) and stmt.args.get("into"):
            issues.append("禁止的构造: SELECT INTO")

        return issues

    def get_query_info(self, sql: str) -> dict:
        """
        提取查询信息（用于审计日志）

        Returns:
            dict: 包含表名、列名等信息
        """
        try:
            stmt = sqlglot.parse_one(sql, dialect="postgres")
            return {
                "tables": [t.name for t in stmt.find_all(exp.Table)],
                "columns": [c.name for c in stmt.find_all(exp.Column)],
                "has_where": stmt.find(exp.Where) is not None,
                "has_join": stmt.find(exp.Join) is not None,
                "has_group_by": stmt.find(exp.Group) is not None,
                "has_order_by": stmt.find(exp.Order) is not None,
            }
        except Exception:
            return {}
```

### 3.6 数据库执行器 (asyncpg)

使用 asyncpg 连接池管理数据库连接，执行只读查询。使用 AST 方式处理 LIMIT，并通过 `limit + 1` 策略准确检测截断。

```python
# pg_mcp/services/executor.py
import asyncpg
import sqlglot
from sqlglot import exp
from asyncpg import Pool
from datetime import datetime, timezone
from pydantic import BaseModel
from pg_mcp.config.settings import DatabaseConfig, QueryConfig
from pg_mcp.exceptions.errors import QueryTimeoutError

class QueryResult(BaseModel):
    """查询结果模型"""
    columns: list[str]
    rows: list[list]
    row_count: int
    truncated: bool
    execution_time_ms: int


class SQLExecutor:
    """SQL 执行器 - 基于 asyncpg 连接池"""

    def __init__(self, query_config: QueryConfig):
        self.query_config = query_config
        self._pools: dict[str, Pool] = {}

    async def initialize(self, databases: list[DatabaseConfig]):
        """初始化所有数据库连接池"""
        for db_config in databases:
            pool = await asyncpg.create_pool(
                host=db_config.host,
                port=db_config.port,
                database=db_config.database,
                user=db_config.username,
                password=db_config.password.get_secret_value(),
                min_size=db_config.min_connections,
                max_size=db_config.max_connections,
                ssl=db_config.ssl_mode,
                # 强制只读事务
                server_settings={
                    "default_transaction_read_only": "on"
                }
            )
            self._pools[db_config.name] = pool

    def get_pool(self, db_name: str) -> Pool | None:
        """获取数据库连接池（公开访问器）"""
        return self._pools.get(db_name)

    async def close(self):
        """关闭所有连接池"""
        for pool in self._pools.values():
            await pool.close()

    async def execute(
        self,
        db_name: str,
        sql: str,
        limit: int = 100
    ) -> QueryResult:
        """
        执行 SQL 查询

        Args:
            db_name: 数据库名称
            sql: SQL 语句
            limit: 结果行数限制

        Returns:
            QueryResult: 查询结果
        """
        pool = self._pools.get(db_name)
        if not pool:
            raise ValueError(f"数据库连接池不存在: {db_name}")

        start_time = datetime.now(timezone.utc)

        async with pool.acquire() as conn:
            try:
                # 设置语句超时
                await conn.execute(
                    f"SET statement_timeout = '{self.query_config.timeout_seconds}s'"
                )

                # 使用 AST 方式添加/修改 LIMIT 子句
                # 获取 limit + 1 行以准确检测截断
                limited_sql = self._ensure_limit_via_ast(sql, limit + 1)

                # 执行查询
                rows = await conn.fetch(limited_sql)

                # 提取列名
                columns = list(rows[0].keys()) if rows else []

                # 检测是否截断（获取了 limit + 1 行）
                truncated = len(rows) > limit
                if truncated:
                    rows = rows[:limit]  # 只返回 limit 行

                # 转换结果
                result_rows = [list(row.values()) for row in rows]

                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

                return QueryResult(
                    columns=columns,
                    rows=result_rows,
                    row_count=len(result_rows),
                    truncated=truncated,
                    execution_time_ms=int(execution_time)
                )

            except asyncpg.exceptions.QueryCanceledError:
                raise QueryTimeoutError(self.query_config.timeout_seconds)

    def _ensure_limit_via_ast(self, sql: str, limit: int) -> str:
        """使用 AST 方式确保 SQL 有 LIMIT 子句"""
        try:
            stmt = sqlglot.parse_one(sql, dialect="postgres")

            # 检查是否已有 LIMIT
            existing_limit = stmt.find(exp.Limit)
            if existing_limit:
                # 如果已有 LIMIT，取较小值
                existing_value = existing_limit.this
                if isinstance(existing_value, exp.Literal):
                    existing_int = int(existing_value.this)
                    if existing_int <= limit:
                        return sql  # 保持原有 LIMIT
                # 替换为新的 LIMIT
                existing_limit.set("this", exp.Literal.number(limit))
            else:
                # 添加 LIMIT 子句
                stmt = stmt.limit(limit)

            return stmt.sql(dialect="postgres")
        except Exception:
            # AST 解析失败时回退到字符串方式
            sql_stripped = sql.rstrip(";").strip()
            return f"{sql_stripped} LIMIT {limit}"

    async def health_check(self, db_name: str) -> bool:
        """健康检查"""
        try:
            pool = self._pools.get(db_name)
            if not pool:
                return False
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False
```

### 3.7 Schema 发现服务

自动发现并缓存数据库 Schema 信息。优化为批量查询，解决 N+1 问题，并支持 TTL 缓存刷新。

```python
# pg_mcp/services/schema.py
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from asyncpg import Pool
from pg_mcp.config.settings import SchemaCacheConfig

class ColumnInfo(BaseModel):
    """列信息"""
    name: str
    data_type: str
    nullable: bool
    is_primary_key: bool = False
    comment: str | None = None

class TableInfo(BaseModel):
    """表信息"""
    name: str
    schema_name: str
    columns: list[ColumnInfo]
    comment: str | None = None

class SchemaInfo(BaseModel):
    """Schema 信息"""
    database: str
    tables: list[TableInfo]
    cached_at: datetime


class SchemaService:
    """Schema 发现与缓存服务"""

    # 批量 Schema 发现 SQL（解决 N+1 问题）
    BULK_SCHEMA_QUERY = """
        WITH table_info AS (
            SELECT
                t.table_schema,
                t.table_name,
                obj_description(
                    (quote_ident(t.table_schema) || '.' || quote_ident(t.table_name))::regclass
                ) as table_comment
            FROM information_schema.tables t
            WHERE t.table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
              AND t.table_type = 'BASE TABLE'
        ),
        column_info AS (
            SELECT
                c.table_schema,
                c.table_name,
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.ordinal_position,
                col_description(
                    (quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))::regclass,
                    c.ordinal_position
                ) as column_comment
            FROM information_schema.columns c
            WHERE c.table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
        ),
        pk_info AS (
            SELECT
                kcu.table_schema,
                kcu.table_name,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
        )
        SELECT
            t.table_schema,
            t.table_name,
            t.table_comment,
            c.column_name,
            c.data_type,
            c.is_nullable,
            c.ordinal_position,
            c.column_comment,
            CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary_key
        FROM table_info t
        LEFT JOIN column_info c
            ON t.table_schema = c.table_schema AND t.table_name = c.table_name
        LEFT JOIN pk_info pk
            ON c.table_schema = pk.table_schema
            AND c.table_name = pk.table_name
            AND c.column_name = pk.column_name
        ORDER BY t.table_schema, t.table_name, c.ordinal_position
    """

    def __init__(self, cache_config: SchemaCacheConfig | None = None):
        self.cache_config = cache_config or SchemaCacheConfig()
        self._cache: dict[str, SchemaInfo] = {}

    async def discover(self, db_name: str, pool: Pool) -> SchemaInfo:
        """
        发现数据库 Schema（批量查询，单次往返）

        Args:
            db_name: 数据库名称
            pool: asyncpg 连接池

        Returns:
            SchemaInfo: Schema 信息
        """
        async with pool.acquire() as conn:
            # 单次批量查询获取所有信息
            rows = await conn.fetch(self.BULK_SCHEMA_QUERY)

            # 在内存中分组构建 Schema
            tables_dict: dict[tuple[str, str], TableInfo] = {}

            for row in rows:
                key = (row["table_schema"], row["table_name"])

                if key not in tables_dict:
                    tables_dict[key] = TableInfo(
                        name=row["table_name"],
                        schema_name=row["table_schema"],
                        columns=[],
                        comment=row["table_comment"]
                    )

                # 添加列信息（如果存在）
                if row["column_name"]:
                    tables_dict[key].columns.append(ColumnInfo(
                        name=row["column_name"],
                        data_type=row["data_type"],
                        nullable=row["is_nullable"] == "YES",
                        is_primary_key=row["is_primary_key"],
                        comment=row["column_comment"]
                    ))

            schema_info = SchemaInfo(
                database=db_name,
                tables=list(tables_dict.values()),
                cached_at=datetime.now(timezone.utc)
            )

            # 缓存
            self._cache[db_name] = schema_info
            return schema_info

    async def get_schema(self, db_name: str, pool: Pool | None = None) -> SchemaInfo | None:
        """
        获取 Schema 信息（带 TTL 检查）

        Args:
            db_name: 数据库名称
            pool: 可选的连接池，用于自动刷新

        Returns:
            SchemaInfo | None: Schema 信息
        """
        cached = self._cache.get(db_name)

        if cached is None:
            return None

        # 检查 TTL
        ttl = timedelta(minutes=self.cache_config.ttl_minutes)
        if datetime.now(timezone.utc) - cached.cached_at > ttl:
            if self.cache_config.auto_refresh and pool:
                # 自动刷新
                return await self.discover(db_name, pool)
            # 返回过期缓存（但标记）
            return cached

        return cached

    def is_cache_expired(self, db_name: str) -> bool:
        """检查缓存是否过期"""
        cached = self._cache.get(db_name)
        if cached is None:
            return True
        ttl = timedelta(minutes=self.cache_config.ttl_minutes)
        return datetime.now(timezone.utc) - cached.cached_at > ttl

    def invalidate_cache(self, db_name: str | None = None):
        """使缓存失效"""
        if db_name:
            self._cache.pop(db_name, None)
        else:
            self._cache.clear()

    def format_for_llm(self, schema_info: SchemaInfo) -> str:
        """
        格式化 Schema 信息供 LLM 使用

        Returns:
            str: 格式化的 Schema 描述
        """
        lines = [f"数据库: {schema_info.database}", ""]

        for table in schema_info.tables:
            # 表头
            table_desc = f"表: {table.schema_name}.{table.name}"
            if table.comment:
                table_desc += f" -- {table.comment}"
            lines.append(table_desc)

            # 列信息
            for col in table.columns:
                col_desc = f"  - {col.name}: {col.data_type}"
                if col.is_primary_key:
                    col_desc += " [PK]"
                if not col.nullable:
                    col_desc += " NOT NULL"
                if col.comment:
                    col_desc += f" -- {col.comment}"
                lines.append(col_desc)

            lines.append("")

        return "\n".join(lines)
```

### 3.8 LLM 服务 (DeepSeek)

集成 DeepSeek API 进行自然语言到 SQL 的转换，支持指数退避重试。

```python
# pg_mcp/services/llm.py
import asyncio
import httpx
from pg_mcp.config.settings import DeepSeekConfig
from pg_mcp.services.schema import SchemaInfo, SchemaService
from pg_mcp.exceptions.errors import SQLGenerationError

class LLMService:
    """DeepSeek LLM 服务 - 自然语言转 SQL"""

    SYSTEM_PROMPT = """你是一个 PostgreSQL SQL 专家。根据用户的自然语言描述和数据库 Schema 信息，生成对应的 SQL 查询语句。

规则：
1. 只生成 SELECT 查询语句，禁止任何数据修改操作（INSERT/UPDATE/DELETE/DROP 等）
2. 使用标准 PostgreSQL 语法
3. 只返回 SQL 语句，不要包含任何解释或 markdown 格式
4. 如果用户请求涉及数据修改，返回 "ERROR: 仅支持查询操作"
5. 合理使用 JOIN、GROUP BY、ORDER BY 等子句
6. 对于模糊的查询，做出合理的假设并生成 SQL"""

    def __init__(self, config: DeepSeekConfig, schema_service: SchemaService):
        self.config = config
        self.schema_service = schema_service
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            headers={"Authorization": f"Bearer {config.api_key.get_secret_value()}"}
        )

    async def generate_sql(
        self,
        natural_query: str,
        schema_info: SchemaInfo,
        dialect: str = "postgres"
    ) -> str:
        """
        将自然语言转换为 SQL

        Args:
            natural_query: 自然语言查询描述
            schema_info: 数据库 Schema 信息
            dialect: SQL 方言

        Returns:
            str: 生成的 SQL 语句
        """
        # 格式化 Schema 信息
        schema_text = self.schema_service.format_for_llm(schema_info)

        # 构建用户消息
        user_message = f"""数据库 Schema 信息：
{schema_text}

用户查询：{natural_query}

请生成对应的 SQL 查询语句："""

        # 调用 DeepSeek API（带指数退避重试）
        response = await self._call_api_with_retry(user_message)

        # 清理响应（移除可能的 markdown 格式）
        sql = self._clean_sql_response(response)

        return sql

    async def _call_api_with_retry(self, user_message: str) -> str:
        """调用 DeepSeek API（带指数退避重试）"""
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        }

        last_error: Exception | None = None

        for attempt in range(self.config.max_retries):
            try:
                response = await self._client.post(
                    "/chat/completions",
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]

            except httpx.HTTPStatusError as e:
                last_error = e
                # 429 (Rate Limit) 或 5xx 错误时重试
                if e.response.status_code in (429, 500, 502, 503, 504):
                    await self._exponential_backoff(attempt)
                else:
                    raise SQLGenerationError(f"API 错误: {e.response.status_code}")

            except httpx.TimeoutException as e:
                last_error = e
                await self._exponential_backoff(attempt)

            except Exception as e:
                last_error = e
                await self._exponential_backoff(attempt)

        raise SQLGenerationError(f"重试 {self.config.max_retries} 次后仍失败: {last_error}")

    async def _exponential_backoff(self, attempt: int):
        """指数退避延迟"""
        delay = self.config.retry_base_delay * (2 ** attempt)
        # 添加抖动（±25%）
        import random
        jitter = delay * 0.25 * (random.random() * 2 - 1)
        await asyncio.sleep(delay + jitter)

    def _clean_sql_response(self, response: str) -> str:
        """清理 LLM 响应，提取纯 SQL"""
        sql = response.strip()

        # 移除 markdown 代码块
        if sql.startswith("```sql"):
            sql = sql[6:]
        elif sql.startswith("```"):
            sql = sql[3:]

        if sql.endswith("```"):
            sql = sql[:-3]

        return sql.strip()

    async def close(self):
        """关闭 HTTP 客户端"""
        await self._client.aclose()
```

---

## 4. 数据模型

### 4.1 请求/响应模型

统一的请求和响应模型定义，使用 UTC 时区时间戳。

```python
# pg_mcp/models/request.py
from pydantic import BaseModel, Field
from typing import Literal

ReturnMode = Literal["sql", "result", "both"]

class QueryRequest(BaseModel):
    """查询请求模型"""
    query: str = Field(..., description="自然语言查询描述")
    database: str | None = Field(None, description="目标数据库名称")
    return_mode: ReturnMode = Field("both", description="返回模式")
    limit: int = Field(100, ge=1, le=1000, description="结果行数限制")


# pg_mcp/models/response.py
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Any
import uuid

class QueryResultData(BaseModel):
    """查询结果数据"""
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool

class ValidationInfo(BaseModel):
    """验证信息（可选）"""
    status: str  # passed | warning | failed
    confidence: int = Field(ge=0, le=100)
    message: str | None = None

class QueryMetadata(BaseModel):
    """查询元数据"""
    database: str
    execution_time_ms: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class QueryResponseData(BaseModel):
    """查询响应数据"""
    sql: str | None = None
    result: QueryResultData | None = None
    validation: ValidationInfo | None = None
    metadata: QueryMetadata | None = None

class QueryResponse(BaseModel):
    """成功响应"""
    success: bool = True
    data: QueryResponseData | dict
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class ErrorResponse(BaseModel):
    """错误响应 - 统一格式"""
    success: bool = False
    code: str
    message: str
    details: dict | None = None
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_dump(self, **kwargs):
        """序列化为字典"""
        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details
            },
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat()
        }
```

---

## 5. 生命周期管理

### 5.1 服务启动流程

使用依赖注入容器管理服务生命周期，支持启动失败时的资源清理。

```python
# pg_mcp/__main__.py
import asyncio
from contextlib import asynccontextmanager
from pg_mcp.server import mcp
from pg_mcp.config.settings import Settings
from pg_mcp.services.llm import LLMService
from pg_mcp.services.executor import SQLExecutor
from pg_mcp.services.schema import SchemaService
from pg_mcp.security.validator import SQLValidator
from pg_mcp.context import AppContext, set_context

@asynccontextmanager
async def lifespan(app):
    """应用生命周期管理（带失败清理）"""
    executor = None
    llm_service = None

    try:
        # === 启动阶段 ===

        # 1. 加载配置
        settings = Settings()

        # 2. 初始化 SQL 校验器
        validator = SQLValidator(settings.security)

        # 3. 初始化数据库执行器
        executor = SQLExecutor(settings.query)
        await executor.initialize(settings.databases)

        # 4. 初始化 Schema 服务并发现 Schema
        schema_service = SchemaService(settings.schema_cache)
        for db_config in settings.databases:
            pool = executor.get_pool(db_config.name)
            if pool:
                await schema_service.discover(db_config.name, pool)

        # 5. 初始化 LLM 服务
        llm_service = LLMService(settings.deepseek, schema_service)

        # 6. 创建并设置应用上下文
        ctx = AppContext(
            settings=settings,
            validator=validator,
            executor=executor,
            schema_service=schema_service,
            llm_service=llm_service
        )
        set_context(ctx)

        print(f"✓ {settings.server_name} 启动完成")
        print(f"  - 已连接数据库: {[db.name for db in settings.databases]}")

        yield

    except Exception as e:
        print(f"✗ 启动失败: {e}")
        raise

    finally:
        # === 关闭阶段（确保资源清理）===
        if llm_service:
            await llm_service.close()
        if executor:
            await executor.close()
        print(f"✓ 服务已关闭")


# 注册生命周期
mcp.lifespan = lifespan

if __name__ == "__main__":
    mcp.run()
```

### 5.2 启动时序图

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Settings │     │ Validator│     │ Executor │     │  Schema  │     │   LLM    │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │                │
     │ 1. 加载配置    │                │                │                │
     │◄───────────────│                │                │                │
     │                │                │                │                │
     │                │ 2. 初始化校验器│                │                │
     │                │◄───────────────│                │                │
     │                │                │                │                │
     │                │                │ 3. 创建连接池  │                │
     │                │                │◄───────────────│                │
     │                │                │                │                │
     │                │                │                │ 4. 发现 Schema │
     │                │                │                │◄───────────────│
     │                │                │                │                │
     │                │                │                │                │ 5. 初始化 LLM
     │                │                │                │                │◄──────────
     │                │                │                │                │
     ▼                ▼                ▼                ▼                ▼
                              服务就绪，等待请求
```

---

## 6. 查询处理流程

### 6.1 详细流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          query_database 处理流程                             │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────┐
                              │  接收请求   │
                              │ (query, db) │
                              └──────┬──────┘
                                     │
                                     ▼
                              ┌─────────────┐
                              │ 解析数据库  │
                              │   配置      │
                              └──────┬──────┘
                                     │
                         ┌───────────┴───────────┐
                         │ 数据库存在?           │
                         └───────────┬───────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │ No             │                │ Yes
                    ▼                │                ▼
             ┌─────────────┐        │         ┌─────────────┐
             │ 返回错误    │        │         │ 获取 Schema │
             │ DB_NOT_FOUND│        │         │   信息      │
             └─────────────┘        │         └──────┬──────┘
                                    │                │
                                    │                ▼
                                    │         ┌─────────────┐
                                    │         │ 调用 LLM    │
                                    │         │ 生成 SQL    │
                                    │         └──────┬──────┘
                                    │                │
                                    │                ▼
                                    │         ┌─────────────┐
                                    │         │ SQLGlot     │
                                    │         │ 安全校验    │
                                    │         └──────┬──────┘
                                    │                │
                                    │    ┌───────────┴───────────┐
                                    │    │ 校验通过?             │
                                    │    └───────────┬───────────┘
                                    │                │
                                    │   ┌────────────┼────────────┐
                                    │   │ No         │            │ Yes
                                    │   ▼            │            ▼
                                    │ ┌─────────────┐│     ┌─────────────┐
                                    │ │ 返回错误    ││     │ return_mode │
                                    │ │ SECURITY_   ││     │ 判断        │
                                    │ │ VIOLATION   ││     └──────┬──────┘
                                    │ └─────────────┘│            │
                                    │                │  ┌─────────┴─────────┐
                                    │                │  │                   │
                                    │                │  ▼                   ▼
                                    │                │ "sql"          "result"/"both"
                                    │                │  │                   │
                                    │                │  │                   ▼
                                    │                │  │            ┌─────────────┐
                                    │                │  │            │ asyncpg     │
                                    │                │  │            │ 执行查询    │
                                    │                │  │            └──────┬──────┘
                                    │                │  │                   │
                                    │                │  │                   ▼
                                    │                │  │            ┌─────────────┐
                                    │                │  │            │ 格式化结果  │
                                    │                │  │            └──────┬──────┘
                                    │                │  │                   │
                                    │                │  └─────────┬─────────┘
                                    │                │            │
                                    │                │            ▼
                                    │                │     ┌─────────────┐
                                    │                │     │ 返回响应    │
                                    │                │     │ QueryResponse│
                                    │                │     └─────────────┘
                                    │                │
                                    └────────────────┘
```

### 6.2 错误处理策略

| 阶段 | 错误类型 | 处理策略 | 错误码 |
|------|----------|----------|--------|
| 配置解析 | 数据库不存在 | 返回错误 | `DB_NOT_FOUND` |
| Schema 获取 | 缓存未就绪 | 返回错误 | `SCHEMA_NOT_READY` |
| LLM 调用 | API 超时/失败 | 重试 3 次后返回错误 | `SQL_GENERATION_ERROR` |
| SQL 校验 | 非只读操作 | 拒绝执行 | `SECURITY_VIOLATION` |
| SQL 执行 | 语法错误 | 返回错误 | `QUERY_EXECUTION_ERROR` |
| SQL 执行 | 超时 | 取消查询 | `QUERY_TIMEOUT` |

---

## 7. 安全设计

### 7.1 安全层次

```
┌─────────────────────────────────────────────────────────────────┐
│                        安全防护层次                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: LLM Prompt 约束                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • System Prompt 明确禁止生成非 SELECT 语句               │   │
│  │ • 用户输入与系统提示分离                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ▼                                  │
│  Layer 2: SQLGlot AST 校验                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • 解析 SQL 为 AST                                        │   │
│  │ • 检查语句类型（仅允许 SELECT）                          │   │
│  │ • 检查危险函数调用                                       │   │
│  │ • 检查子查询中的写操作                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ▼                                  │
│  Layer 3: 数据库层约束                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • 使用只读数据库角色                                     │   │
│  │ • 设置 default_transaction_read_only=on                  │   │
│  │ • 语句超时限制                                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 SQLGlot 校验规则（白名单模式）

| 规则 | 检查内容 | 处理 |
|------|----------|------|
| 顶层语句 | 必须是 SELECT 或 WITH (CTE) | 拒绝其他类型 |
| AST 白名单 | 仅允许配置中列出的节点类型 | 拒绝未知节点 |
| 危险语句 | INSERT/UPDATE/DELETE/DROP/CREATE/ALTER | 拒绝 |
| 危险构造 | SELECT INTO, COPY, LOCK | 拒绝 |
| 危险函数 | pg_sleep, lo_export, pg_read_file 等 | 拒绝 |
| 子查询 | 递归检查所有子查询 | 应用相同规则 |

---

## 8. 配置示例

### 8.1 环境变量 (.env)

```bash
# 数据库配置
DB_PASSWORD=your_secure_password
ANALYTICS_DB_URL=postgresql://user:pass@host:5432/analytics

# LLM API Keys
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx  # 可选

# 服务配置
PG_MCP_LOG_LEVEL=INFO
```

### 8.2 配置文件 (config.yaml)

```yaml
server_name: "pg-mcp-server"
log_level: "INFO"

databases:
  - name: "default_db"
    host: "localhost"
    port: 5432
    database: "myapp"
    username: "readonly_user"
    password: "${DB_PASSWORD}"
    ssl_mode: "prefer"
    min_connections: 2
    max_connections: 10
    is_default: true

deepseek:
  api_key: "${DEEPSEEK_API_KEY}"
  model: "deepseek-chat"
  temperature: 0.1
  max_tokens: 2000
  timeout_seconds: 30
  max_retries: 3
  retry_base_delay: 1.0

query:
  timeout_seconds: 30
  max_rows: 100
  max_rows_limit: 1000
  default_return_mode: "both"

schema_cache:
  ttl_minutes: 60
  auto_refresh: true

security:
  allowed_statement_types:
    - "Select"
  blocked_functions:
    - "pg_sleep"
    - "lo_export"
    - "lo_import"
    - "pg_read_file"
    - "pg_write_file"
    - "pg_read_binary_file"
    - "pg_ls_dir"
    - "pg_stat_file"
    - "pg_terminate_backend"
    - "pg_cancel_backend"
  blocked_constructs:
    - "Into"
    - "Copy"
    - "Lock"
  enable_prompt_injection_check: true
```

### 8.3 Claude Desktop 配置

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

---

## 9. 依赖清单

### 9.1 Python 依赖 (pyproject.toml)

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

---

## 10. 测试策略

### 10.1 单元测试

| 模块 | 测试重点 |
|------|----------|
| SQLValidator | 各类 SQL 语句的安全校验 |
| SchemaService | Schema 发现与格式化 |
| LLMService | API 调用与响应解析 |
| SQLExecutor | 查询执行与结果转换 |

### 10.2 SQL 安全校验测试用例

```python
# tests/test_validator.py
import pytest
from pg_mcp.security.validator import SQLValidator, ValidationResult
from pg_mcp.config.settings import SecurityConfig

@pytest.fixture
def validator():
    return SQLValidator(SecurityConfig())

class TestSQLValidator:
    """SQL 安全校验测试（白名单模式）"""

    # === 允许的查询 ===

    def test_simple_select_allowed(self, validator):
        result = validator.validate("SELECT * FROM users")
        assert result.is_safe

    def test_select_with_where_allowed(self, validator):
        result = validator.validate("SELECT name FROM users WHERE id = 1")
        assert result.is_safe

    def test_select_with_join_allowed(self, validator):
        sql = "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id"
        result = validator.validate(sql)
        assert result.is_safe

    def test_cte_select_allowed(self, validator):
        sql = """
        WITH active_users AS (
            SELECT * FROM users WHERE status = 'active'
        )
        SELECT * FROM active_users
        """
        result = validator.validate(sql)
        assert result.is_safe

    def test_complex_select_allowed(self, validator):
        sql = """
        SELECT u.name, COUNT(o.id) as order_count
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        WHERE u.created_at > '2024-01-01'
        GROUP BY u.id, u.name
        HAVING COUNT(o.id) > 5
        ORDER BY order_count DESC
        LIMIT 10
        """
        result = validator.validate(sql)
        assert result.is_safe

    # === 禁止的语句类型 ===

    def test_insert_blocked(self, validator):
        result = validator.validate("INSERT INTO users VALUES (1, 'test')")
        assert not result.is_safe
        assert any("INSERT" in issue or "Insert" in issue for issue in result.detected_issues)

    def test_update_blocked(self, validator):
        result = validator.validate("UPDATE users SET name = 'test' WHERE id = 1")
        assert not result.is_safe

    def test_delete_blocked(self, validator):
        result = validator.validate("DELETE FROM users WHERE id = 1")
        assert not result.is_safe

    def test_drop_blocked(self, validator):
        result = validator.validate("DROP TABLE users")
        assert not result.is_safe

    def test_truncate_blocked(self, validator):
        result = validator.validate("TRUNCATE TABLE users")
        assert not result.is_safe

    # === 禁止的构造 ===

    def test_select_into_blocked(self, validator):
        result = validator.validate("SELECT * INTO new_table FROM users")
        assert not result.is_safe
        assert any("INTO" in issue for issue in result.detected_issues)

    # === 禁止的函数 ===

    def test_pg_sleep_blocked(self, validator):
        result = validator.validate("SELECT pg_sleep(10)")
        assert not result.is_safe
        assert any("pg_sleep" in issue for issue in result.detected_issues)

    def test_lo_export_blocked(self, validator):
        result = validator.validate("SELECT lo_export(12345, '/tmp/file')")
        assert not result.is_safe

    def test_pg_read_file_blocked(self, validator):
        result = validator.validate("SELECT pg_read_file('/etc/passwd')")
        assert not result.is_safe

    # === 子查询安全 ===

    def test_subquery_with_delete_blocked(self, validator):
        sql = "SELECT * FROM (DELETE FROM users RETURNING *) AS deleted"
        result = validator.validate(sql)
        assert not result.is_safe

    def test_subquery_select_allowed(self, validator):
        sql = "SELECT * FROM (SELECT id, name FROM users) AS subq"
        result = validator.validate(sql)
        assert result.is_safe

    # === 边界情况 ===

    def test_empty_sql_blocked(self, validator):
        result = validator.validate("")
        assert not result.is_safe

    def test_invalid_sql_blocked(self, validator):
        result = validator.validate("NOT VALID SQL AT ALL")
        assert not result.is_safe
```

---

## 11. 部署架构

### 11.1 本地开发

```bash
# 安装依赖
pip install -e ".[dev]"

# 运行服务
python -m pg_mcp
```

### 11.2 Docker 部署

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "pg_mcp"]
```

---

## 12. 附录

### 12.1 PRD 需求映射

| PRD 需求 | 设计实现 |
|----------|----------|
| FR-001 数据库连接配置 | Pydantic Settings + DatabaseConfig |
| FR-002 Schema 自动发现 | SchemaService.discover() |
| FR-004 自然语言输入解析 | query_database Tool 参数 |
| FR-005 SQL 生成 | LLMService.generate_sql() |
| FR-006 SQL 安全校验 | SQLValidator (SQLGlot) |
| FR-007 SQL 执行 | SQLExecutor (asyncpg) |
| FR-009 MCP Tools | FastMCP @mcp.tool() |

### 12.2 修订历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0.0 | 2026-02-23 | 初始版本 |
| 1.1.0 | 2026-02-23 | 根据 Codex Review 反馈优化：<br>- 配置类改为 BaseModel（嵌套类）<br>- 添加 AppContext 依赖注入容器<br>- SQL 校验器改为白名单模式<br>- 添加类型化异常定义<br>- Schema 发现优化为批量查询（解决 N+1）<br>- 添加缓存 TTL 和自动刷新<br>- LLM 重试添加指数退避<br>- LIMIT 处理改为 AST 方式<br>- 统一错误响应格式<br>- 使用 UTC 时区时间戳<br>- 扩展测试用例覆盖 |


