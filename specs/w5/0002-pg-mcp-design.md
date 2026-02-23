# PostgreSQL MCP Server 技术设计文档

> 版本: 1.0.0
> 创建日期: 2026-02-23
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
3. **安全纵深**：SQLGlot AST 校验 + 数据库只读角色双重防护
4. **关注点分离**：清晰的模块边界，便于测试和维护

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
│   └── validator.py         # SQLGlot SQL 安全校验
├── models/
│   ├── __init__.py
│   ├── schema.py            # Schema 数据模型
│   ├── request.py           # 请求模型
│   └── response.py          # 响应模型
└── utils/
    ├── __init__.py
    └── logging.py           # 日志工具
```

---

## 3. 核心模块设计

### 3.1 配置管理 (Pydantic Settings)

使用 `pydantic-settings` 实现类型安全的配置管理，支持环境变量和配置文件。

```python
# pg_mcp/config/settings.py
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class DatabaseConfig(BaseSettings):
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

class DeepSeekConfig(BaseSettings):
    """DeepSeek LLM 配置"""
    api_key: SecretStr = Field(..., alias="DEEPSEEK_API_KEY")
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    temperature: float = 0.1
    max_tokens: int = 2000
    timeout_seconds: int = 30
    max_retries: int = 3

class QueryConfig(BaseSettings):
    """查询执行配置"""
    timeout_seconds: int = 30
    max_rows: int = 100
    max_rows_limit: int = 1000
    default_return_mode: str = "both"  # sql | result | both

class SecurityConfig(BaseSettings):
    """安全配置"""
    allowed_statements: list[str] = ["SELECT"]
    blocked_functions: list[str] = [
        "pg_sleep", "lo_export", "lo_import",
        "pg_read_file", "pg_write_file"
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

    @property
    def default_database(self) -> DatabaseConfig | None:
        """获取默认数据库配置"""
        for db in self.databases:
            if db.is_default:
                return db
        return self.databases[0] if self.databases else None
```

### 3.2 FastMCP Server 定义

使用 FastMCP 装饰器定义 MCP Tool。

```python
# pg_mcp/server.py
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Literal
from pg_mcp.config.settings import Settings
from pg_mcp.services.llm import LLMService
from pg_mcp.services.executor import SQLExecutor
from pg_mcp.services.schema import SchemaService
from pg_mcp.security.validator import SQLValidator
from pg_mcp.models.response import QueryResponse, ErrorResponse

# 初始化 FastMCP Server
mcp = FastMCP("pg-mcp-server")

# 全局服务实例（在 lifespan 中初始化）
settings: Settings = None
llm_service: LLMService = None
executor: SQLExecutor = None
schema_service: SchemaService = None
validator: SQLValidator = None


class QueryInput(BaseModel):
    """query_database 工具输入参数"""
    query: str = Field(..., description="自然语言查询描述")
    database: str | None = Field(None, description="目标数据库名称")
    return_mode: Literal["sql", "result", "both"] = Field(
        "both", description="返回模式"
    )
    limit: int = Field(100, ge=1, le=1000, description="结果行数限制")


@mcp.tool()
async def query_database(
    query: str,
    database: str | None = None,
    return_mode: str = "both",
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
    try:
        # 1. 确定目标数据库
        db_config = _get_database_config(database)
        if not db_config:
            return ErrorResponse(
                code="DB_NOT_FOUND",
                message=f"数据库 '{database}' 未配置"
            ).model_dump()

        # 2. 获取 Schema 信息
        schema_info = await schema_service.get_schema(db_config.name)

        # 3. 调用 LLM 生成 SQL
        generated_sql = await llm_service.generate_sql(
            natural_query=query,
            schema_info=schema_info,
            dialect="postgres"
        )

        # 4. SQL 安全校验
        validation_result = validator.validate(generated_sql)
        if not validation_result.is_safe:
            return ErrorResponse(
                code="SECURITY_VIOLATION",
                message=validation_result.message,
                details={"detected": validation_result.detected_issues}
            ).model_dump()

        # 5. 根据 return_mode 决定是否执行
        response_data = {"sql": generated_sql}

        if return_mode in ("result", "both"):
            # 执行 SQL
            result = await executor.execute(
                db_name=db_config.name,
                sql=generated_sql,
                limit=min(limit, settings.query.max_rows_limit)
            )
            response_data["result"] = result.model_dump()

        if return_mode == "result":
            del response_data["sql"]

        return QueryResponse(
            success=True,
            data=response_data
        ).model_dump()

    except Exception as e:
        return ErrorResponse(
            code="QUERY_EXECUTION_ERROR",
            message=str(e)
        ).model_dump()


def _get_database_config(db_name: str | None):
    """获取数据库配置"""
    if db_name is None:
        return settings.default_database
    for db in settings.databases:
        if db.name == db_name:
            return db
    return None
```

### 3.3 SQL 安全校验器 (SQLGlot)

使用 SQLGlot 解析 SQL AST，进行语法级别的安全校验。

```python
# pg_mcp/security/validator.py
import sqlglot
from sqlglot import exp
from dataclasses import dataclass
from pg_mcp.config.settings import SecurityConfig

@dataclass
class ValidationResult:
    """校验结果"""
    is_safe: bool
    message: str = ""
    detected_issues: list[str] = None

    def __post_init__(self):
        if self.detected_issues is None:
            self.detected_issues = []


class SQLValidator:
    """SQL 安全校验器 - 基于 SQLGlot AST 分析"""

    # 危险语句类型映射
    DANGEROUS_STATEMENTS = {
        exp.Insert: "INSERT",
        exp.Update: "UPDATE",
        exp.Delete: "DELETE",
        exp.Drop: "DROP",
        exp.Create: "CREATE",
        exp.Alter: "ALTER",
        exp.Truncate: "TRUNCATE",
        exp.Grant: "GRANT",
        exp.Revoke: "REVOKE",
    }

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.blocked_functions = set(f.lower() for f in config.blocked_functions)

    def validate(self, sql: str) -> ValidationResult:
        """
        校验 SQL 语句安全性

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

        issues = []

        for stmt in statements:
            # 检查语句类型
            stmt_issues = self._check_statement_type(stmt)
            issues.extend(stmt_issues)

            # 检查危险函数
            func_issues = self._check_dangerous_functions(stmt)
            issues.extend(func_issues)

            # 检查子查询中的写操作
            subquery_issues = self._check_subqueries(stmt)
            issues.extend(subquery_issues)

        if issues:
            return ValidationResult(
                is_safe=False,
                message="检测到非只读操作，本服务仅支持 SELECT 查询",
                detected_issues=issues
            )

        return ValidationResult(is_safe=True, message="校验通过")

    def _check_statement_type(self, stmt: exp.Expression) -> list[str]:
        """检查语句类型是否允许"""
        issues = []

        for dangerous_type, name in self.DANGEROUS_STATEMENTS.items():
            if isinstance(stmt, dangerous_type):
                issues.append(f"禁止的语句类型: {name}")

        # 确保是 SELECT 语句
        if not isinstance(stmt, exp.Select):
            # 允许 WITH (CTE) 语句，但内部必须是 SELECT
            if isinstance(stmt, exp.With):
                # 检查 WITH 的主体是否为 SELECT
                if not isinstance(stmt.this, exp.Select):
                    issues.append("WITH 语句的主体必须是 SELECT")
            elif stmt.__class__.__name__ not in ["Select"]:
                issues.append(f"不支持的语句类型: {stmt.__class__.__name__}")

        return issues

    def _check_dangerous_functions(self, stmt: exp.Expression) -> list[str]:
        """检查是否调用了危险函数"""
        issues = []

        for func in stmt.find_all(exp.Func):
            func_name = func.name.lower() if hasattr(func, 'name') else ""
            if func_name in self.blocked_functions:
                issues.append(f"禁止的函数调用: {func_name}")

        # 检查匿名函数调用
        for anon in stmt.find_all(exp.Anonymous):
            func_name = anon.this.lower() if isinstance(anon.this, str) else ""
            if func_name in self.blocked_functions:
                issues.append(f"禁止的函数调用: {func_name}")

        return issues

    def _check_subqueries(self, stmt: exp.Expression) -> list[str]:
        """检查子查询中是否有写操作"""
        issues = []

        for subquery in stmt.find_all(exp.Subquery):
            inner = subquery.this
            for dangerous_type, name in self.DANGEROUS_STATEMENTS.items():
                if isinstance(inner, dangerous_type):
                    issues.append(f"子查询中禁止的操作: {name}")

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

### 3.4 数据库执行器 (asyncpg)

使用 asyncpg 连接池管理数据库连接，执行只读查询。

```python
# pg_mcp/services/executor.py
import asyncpg
from asyncpg import Pool
from datetime import datetime
from pydantic import BaseModel
from pg_mcp.config.settings import DatabaseConfig, QueryConfig

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

        start_time = datetime.now()

        async with pool.acquire() as conn:
            # 设置语句超时
            await conn.execute(
                f"SET statement_timeout = '{self.query_config.timeout_seconds}s'"
            )

            # 添加 LIMIT 子句（如果原 SQL 没有）
            limited_sql = self._ensure_limit(sql, limit)

            # 执行查询
            rows = await conn.fetch(limited_sql)

            # 提取列名
            columns = list(rows[0].keys()) if rows else []

            # 转换结果
            result_rows = [list(row.values()) for row in rows]

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return QueryResult(
                columns=columns,
                rows=result_rows,
                row_count=len(result_rows),
                truncated=len(result_rows) >= limit,
                execution_time_ms=int(execution_time)
            )

    def _ensure_limit(self, sql: str, limit: int) -> str:
        """确保 SQL 有 LIMIT 子句"""
        sql_upper = sql.upper().strip()
        if "LIMIT" not in sql_upper:
            # 移除末尾分号
            sql = sql.rstrip(";").strip()
            return f"{sql} LIMIT {limit}"
        return sql

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

### 3.5 Schema 发现服务

自动发现并缓存数据库 Schema 信息。

```python
# pg_mcp/services/schema.py
from datetime import datetime
from pydantic import BaseModel
from asyncpg import Pool

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

    # Schema 发现 SQL
    TABLES_QUERY = """
        SELECT
            t.table_schema,
            t.table_name,
            obj_description(
                (quote_ident(t.table_schema) || '.' || quote_ident(t.table_name))::regclass
            ) as table_comment
        FROM information_schema.tables t
        WHERE t.table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
          AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_schema, t.table_name
    """

    COLUMNS_QUERY = """
        SELECT
            c.column_name,
            c.data_type,
            c.is_nullable,
            c.column_default,
            col_description(
                (quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))::regclass,
                c.ordinal_position
            ) as column_comment,
            CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary_key
        FROM information_schema.columns c
        LEFT JOIN (
            SELECT kcu.column_name, kcu.table_schema, kcu.table_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
        ) pk ON c.column_name = pk.column_name
            AND c.table_schema = pk.table_schema
            AND c.table_name = pk.table_name
        WHERE c.table_schema = $1 AND c.table_name = $2
        ORDER BY c.ordinal_position
    """

    def __init__(self, excluded_schemas: list[str] = None):
        self.excluded_schemas = excluded_schemas or [
            "pg_catalog", "information_schema", "pg_toast"
        ]
        self._cache: dict[str, SchemaInfo] = {}

    async def discover(self, db_name: str, pool: Pool) -> SchemaInfo:
        """
        发现数据库 Schema

        Args:
            db_name: 数据库名称
            pool: asyncpg 连接池

        Returns:
            SchemaInfo: Schema 信息
        """
        async with pool.acquire() as conn:
            # 获取所有表
            tables_rows = await conn.fetch(self.TABLES_QUERY)

            tables = []
            for table_row in tables_rows:
                # 获取列信息
                columns_rows = await conn.fetch(
                    self.COLUMNS_QUERY,
                    table_row["table_schema"],
                    table_row["table_name"]
                )

                columns = [
                    ColumnInfo(
                        name=col["column_name"],
                        data_type=col["data_type"],
                        nullable=col["is_nullable"] == "YES",
                        is_primary_key=col["is_primary_key"],
                        comment=col["column_comment"]
                    )
                    for col in columns_rows
                ]

                tables.append(TableInfo(
                    name=table_row["table_name"],
                    schema_name=table_row["table_schema"],
                    columns=columns,
                    comment=table_row["table_comment"]
                ))

            schema_info = SchemaInfo(
                database=db_name,
                tables=tables,
                cached_at=datetime.now()
            )

            # 缓存
            self._cache[db_name] = schema_info
            return schema_info

    async def get_schema(self, db_name: str) -> SchemaInfo | None:
        """获取缓存的 Schema 信息"""
        return self._cache.get(db_name)

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

### 3.6 LLM 服务 (DeepSeek)

集成 DeepSeek API 进行自然语言到 SQL 的转换。

```python
# pg_mcp/services/llm.py
import httpx
from pg_mcp.config.settings import DeepSeekConfig
from pg_mcp.services.schema import SchemaInfo, SchemaService

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

        # 调用 DeepSeek API
        response = await self._call_api(user_message)

        # 清理响应（移除可能的 markdown 格式）
        sql = self._clean_sql_response(response)

        return sql

    async def _call_api(self, user_message: str) -> str:
        """调用 DeepSeek API"""
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        }

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
                if attempt == self.config.max_retries - 1:
                    raise RuntimeError(f"DeepSeek API 调用失败: {e}")
            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    raise RuntimeError(f"DeepSeek API 调用异常: {e}")

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

```python
# pg_mcp/models/response.py
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any

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
    generated_at: datetime = Field(default_factory=datetime.now)

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
    request_id: str | None = None

class ErrorDetail(BaseModel):
    """错误详情"""
    code: str
    message: str
    details: dict | None = None
    suggestion: str | None = None

class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: ErrorDetail | None = None
    code: str | None = None  # 简化字段
    message: str | None = None
    details: dict | None = None
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)

    def model_dump(self, **kwargs):
        """兼容简化格式"""
        if self.error:
            return super().model_dump(**kwargs)
        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details
            },
            "timestamp": self.timestamp.isoformat()
        }
```

---

## 5. 生命周期管理

### 5.1 服务启动流程

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
import pg_mcp.server as server_module

@asynccontextmanager
async def lifespan(app):
    """应用生命周期管理"""
    # === 启动阶段 ===

    # 1. 加载配置
    settings = Settings()
    server_module.settings = settings

    # 2. 初始化 SQL 校验器
    validator = SQLValidator(settings.security)
    server_module.validator = validator

    # 3. 初始化数据库执行器
    executor = SQLExecutor(settings.query)
    await executor.initialize(settings.databases)
    server_module.executor = executor

    # 4. 初始化 Schema 服务并发现 Schema
    schema_service = SchemaService()
    for db_config in settings.databases:
        pool = executor._pools.get(db_config.name)
        if pool:
            await schema_service.discover(db_config.name, pool)
    server_module.schema_service = schema_service

    # 5. 初始化 LLM 服务
    llm_service = LLMService(settings.deepseek, schema_service)
    server_module.llm_service = llm_service

    print(f"✓ {settings.server_name} 启动完成")
    print(f"  - 已连接数据库: {[db.name for db in settings.databases]}")

    yield

    # === 关闭阶段 ===
    await llm_service.close()
    await executor.close()
    print(f"✓ {settings.server_name} 已关闭")


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

### 7.2 SQLGlot 校验规则

| 规则 | 检查内容 | 处理 |
|------|----------|------|
| 语句类型 | INSERT/UPDATE/DELETE/DROP/CREATE/ALTER | 拒绝 |
| 危险函数 | pg_sleep, lo_export, pg_read_file 等 | 拒绝 |
| 子查询 | 子查询中的 DML/DDL | 拒绝 |
| CTE | WITH 语句主体必须是 SELECT | 拒绝非 SELECT |

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
  model: "deepseek-chat"
  temperature: 0.1
  max_tokens: 2000
  timeout_seconds: 30
  max_retries: 3

query:
  timeout_seconds: 30
  max_rows: 100
  max_rows_limit: 1000
  default_return_mode: "both"

security:
  allowed_statements:
    - "SELECT"
  blocked_functions:
    - "pg_sleep"
    - "lo_export"
    - "lo_import"
    - "pg_read_file"
    - "pg_write_file"
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
    """SQL 安全校验测试"""

    def test_select_allowed(self, validator):
        result = validator.validate("SELECT * FROM users")
        assert result.is_safe

    def test_insert_blocked(self, validator):
        result = validator.validate("INSERT INTO users VALUES (1, 'test')")
        assert not result.is_safe
        assert "INSERT" in result.detected_issues[0]

    def test_delete_blocked(self, validator):
        result = validator.validate("DELETE FROM users WHERE id = 1")
        assert not result.is_safe

    def test_drop_blocked(self, validator):
        result = validator.validate("DROP TABLE users")
        assert not result.is_safe

    def test_dangerous_function_blocked(self, validator):
        result = validator.validate("SELECT pg_sleep(10)")
        assert not result.is_safe
        assert "pg_sleep" in str(result.detected_issues)

    def test_subquery_with_delete_blocked(self, validator):
        sql = "SELECT * FROM (DELETE FROM users RETURNING *) AS deleted"
        result = validator.validate(sql)
        assert not result.is_safe

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


