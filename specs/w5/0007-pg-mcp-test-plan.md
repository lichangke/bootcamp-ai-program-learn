# PostgreSQL MCP Server 测试计划

> 版本: 1.0.0
> 创建日期: 2026-02-24
> 状态: 草稿
> 关联文档:
> - [0002-pg-mcp-design.md](./0002-pg-mcp-design.md)
> - [0004-pg-mcp-impl-plan.md](./0004-pg-mcp-impl-plan.md)
> - [0001-pg-mcp-prd.md](./0001-pg-mcp-prd.md)

---

## 1. 测试概述

### 1.1 测试目标

本测试计划旨在确保 PostgreSQL MCP Server 的功能完整性、安全性、性能和可靠性，覆盖从单元测试到端到端集成测试的完整测试金字塔。

### 1.2 测试策略

采用**分层测试策略**，遵循测试金字塔原则：

```
        ┌─────────────────┐
        │   E2E 测试      │  ← 少量，覆盖关键用户场景
        │   (5-10 个)     │
        ├─────────────────┤
        │  集成测试       │  ← 中等数量，验证模块协作
        │  (20-30 个)     │
        ├─────────────────┤
        │  单元测试       │  ← 大量，覆盖所有函数/类
        │  (100+ 个)      │
        └─────────────────┘
```

### 1.3 测试范围

| 测试类型 | 覆盖范围 | 目标覆盖率 |
|---------|---------|-----------|
| 单元测试 | 所有模块的独立函数/类 | ≥ 85% |
| 集成测试 | 跨模块交互、数据库集成 | ≥ 70% |
| E2E 测试 | 完整用户场景（MCP 协议） | 核心场景 100% |
| 安全测试 | SQL 注入、权限校验 | 所有攻击向量 |
| 性能测试 | 响应时间、并发处理 | NFR 指标验证 |

### 1.4 测试环境

| 环境 | 用途 | 配置 |
|------|------|------|
| 本地开发 | 单元测试、快速迭代 | Python 3.12 + pytest + mock |
| CI/CD | 自动化测试 | GitHub Actions + PostgreSQL service |
| 集成测试 | 真实数据库交互 | PostgreSQL 16 测试实例 |
| E2E 测试 | 完整 MCP 协议验证 | MCP Inspector + 真实 Claude Desktop |

---

## 2. 测试工具链

### 2.1 核心工具

| 工具 | 版本 | 用途 |
|------|------|------|
| pytest | ≥ 8.0.0 | 测试框架 |
| pytest-asyncio | ≥ 0.23.0 | 异步测试支持 |
| pytest-cov | ≥ 4.1.0 | 代码覆盖率统计 |
| pytest-mock | ≥ 3.12.0 | Mock/Spy 工具 |
| httpx-mock | ≥ 0.12.0 | HTTP 请求 Mock |
| postgresql-client | ≥ 14 | 测试数据库初始化（可选） |
| faker | ≥ 22.0.0 | 测试数据生成 |

### 2.2 辅助工具

| 工具 | 用途 |
|------|------|
| ruff | 代码质量检查 |
| mypy | 静态类型检查 |
| bandit | 安全漏洞扫描 |
| locust | 负载测试（可选） |

---

## 3. 单元测试计划

### 3.1 配置管理模块 (pg_mcp/config/settings.py)

#### 测试套件: TestSettings

**测试用例:**

| 用例 ID | 测试场景 | 输入 | 期望输出 | 优先级 |
|---------|---------|------|----------|--------|
| UT-CFG-001 | 从环境变量加载完整配置 | 所有必需环境变量 | Settings 对象正确初始化 | P0 |
| UT-CFG-002 | 缺少必需配置项 | 缺少 DB_HOST | ValidationError | P0 |
| UT-CFG-003 | 密码脱敏验证 | DB_PASSWORD="secret" | str(settings) 不包含 "secret" | P0 |
| UT-CFG-004 | 默认值生效 | 未设置 DB_PORT | port=5432 | P1 |
| UT-CFG-005 | 无效端口号 | DB_PORT="abc" | ValidationError | P1 |
| UT-CFG-006 | 连接池配置验证 | min_size > max_size | ValidationError | P1 |
| UT-CFG-007 | LLM 配置加载 | DEEPSEEK_API_KEY | LLMConfig 正确初始化 | P0 |
| UT-CFG-008 | 缓存 TTL 边界值 | CACHE_TTL=0 | ValidationError (必须 > 0) | P2 |

**实现示例:**

```python
# tests/unit/config/test_settings.py
import pytest
from pydantic import ValidationError
from pg_mcp.config.settings import Settings, DatabaseConfig

class TestSettings:
    def test_load_from_env_success(self, monkeypatch):
        """UT-CFG-001: 从环境变量加载完整配置"""
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PORT", "5432")
        monkeypatch.setenv("DB_NAME", "testdb")
        monkeypatch.setenv("DB_USER", "testuser")
        monkeypatch.setenv("DB_PASSWORD", "testpass")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

        settings = Settings()
        assert settings.database.host == "localhost"
        assert settings.database.port == 5432
        assert settings.llm.api_key.get_secret_value() == "sk-test"

    def test_missing_required_field(self, monkeypatch):
        """UT-CFG-002: 缺少必需配置项"""
        monkeypatch.delenv("DB_HOST", raising=False)
        with pytest.raises(ValidationError) as exc_info:
            Settings()
        assert "DB_HOST" in str(exc_info.value)

    def test_password_masking(self, monkeypatch):
        """UT-CFG-003: 密码脱敏验证"""
        monkeypatch.setenv("DB_PASSWORD", "super_secret_password")
        settings = Settings()
        settings_str = str(settings)
        assert "super_secret_password" not in settings_str
        assert "**********" in settings_str or "SecretStr" in settings_str
```

### 3.2 异常体系模块 (pg_mcp/exceptions/errors.py)

#### 测试套件: TestExceptions

**测试用例:**

| 用例 ID | 测试场景 | 输入 | 期望输出 | 优先级 |
|---------|---------|------|----------|--------|
| UT-EXC-001 | SQLValidationError 创建 | 错误消息 + SQL | 包含 SQL 的异常对象 | P0 |
| UT-EXC-002 | DatabaseError 错误码 | error_code="42P01" | 正确的错误码属性 | P1 |
| UT-EXC-003 | LLMError 重试信息 | retry_count=3 | 包含重试次数 | P1 |
| UT-EXC-004 | 异常继承关系 | SQLValidationError | isinstance(PgMcpError) | P0 |

**实现示例:**

```python
# tests/unit/exceptions/test_errors.py
from pg_mcp.exceptions.errors import (
    PgMcpError, SQLValidationError, DatabaseError, LLMError
)

class TestExceptions:
    def test_sql_validation_error_with_sql(self):
        """UT-EXC-001: SQLValidationError 包含 SQL"""
        sql = "DROP TABLE users;"
        error = SQLValidationError("Forbidden operation", sql=sql)
        assert error.sql == sql
        assert "DROP TABLE" in str(error)

    def test_database_error_code(self):
        """UT-EXC-002: DatabaseError 错误码"""
        error = DatabaseError("Table not found", error_code="42P01")
        assert error.error_code == "42P01"

    def test_exception_inheritance(self):
        """UT-EXC-004: 异常继承关系"""
        error = SQLValidationError("test")
        assert isinstance(error, PgMcpError)
        assert isinstance(error, Exception)
```

### 3.3 SQL 安全校验器 (pg_mcp/security/validator.py)

#### 测试套件: TestSQLValidator

**测试用例:**

| 用例 ID | 测试场景 | 输入 SQL | 期望结果 | 优先级 |
|---------|---------|---------|----------|--------|
| UT-VAL-001 | 简单 SELECT 通过 | `SELECT * FROM users` | 通过 | P0 |
| UT-VAL-002 | SELECT 带 WHERE | `SELECT id FROM users WHERE age > 18` | 通过 | P0 |
| UT-VAL-003 | SELECT 带 JOIN | `SELECT u.name FROM users u JOIN orders o ON u.id=o.user_id` | 通过 | P0 |
| UT-VAL-004 | 拒绝 DROP TABLE | `DROP TABLE users;` | SQLValidationError | P0 |
| UT-VAL-005 | 拒绝 DELETE | `DELETE FROM users WHERE id=1` | SQLValidationError | P0 |
| UT-VAL-006 | 拒绝 UPDATE | `UPDATE users SET name='x'` | SQLValidationError | P0 |
| UT-VAL-007 | 拒绝 INSERT | `INSERT INTO users VALUES (1, 'x')` | SQLValidationError | P0 |
| UT-VAL-008 | 拒绝 TRUNCATE | `TRUNCATE TABLE users` | SQLValidationError | P0 |
| UT-VAL-009 | 拒绝 ALTER TABLE | `ALTER TABLE users ADD COLUMN x INT` | SQLValidationError | P0 |
| UT-VAL-010 | 拒绝 CREATE TABLE | `CREATE TABLE test (id INT)` | SQLValidationError | P0 |
| UT-VAL-011 | 拒绝存储过程调用 | `CALL update_user(1)` | SQLValidationError | P0 |
| UT-VAL-012 | 拒绝 COPY 命令 | `COPY users TO '/tmp/data'` | SQLValidationError | P0 |
| UT-VAL-013 | 拒绝多语句 | `SELECT 1; DROP TABLE users;` | SQLValidationError | P0 |
| UT-VAL-014 | CTE 查询通过 | `WITH cte AS (SELECT * FROM users) SELECT * FROM cte` | 通过 | P1 |
| UT-VAL-015 | 子查询通过 | `SELECT * FROM (SELECT id FROM users) t` | 通过 | P1 |
| UT-VAL-016 | 聚合函数通过 | `SELECT COUNT(*), AVG(age) FROM users` | 通过 | P1 |
| UT-VAL-017 | UNION 查询通过 | `SELECT id FROM users UNION SELECT id FROM orders` | 通过 | P1 |
| UT-VAL-018 | 无效 SQL 语法 | `SELECT FROM WHERE` | SQLValidationError | P1 |
| UT-VAL-019 | 空 SQL | `""` | SQLValidationError | P1 |
| UT-VAL-020 | SQL 注释处理 | `SELECT * FROM users -- comment` | 通过 | P2 |

**实现示例:**

```python
# tests/unit/security/test_validator.py
import pytest
from pg_mcp.security.validator import SQLValidator
from pg_mcp.exceptions.errors import SQLValidationError

class TestSQLValidator:
    @pytest.fixture
    def validator(self):
        return SQLValidator()

    def test_simple_select_passes(self, validator):
        """UT-VAL-001: 简单 SELECT 通过"""
        sql = "SELECT * FROM users"
        result = validator.validate(sql)
        assert result.is_valid is True
        assert result.sanitized_sql == sql

    @pytest.mark.parametrize("sql,operation", [
        ("DROP TABLE users;", "DROP"),
        ("DELETE FROM users WHERE id=1", "DELETE"),
        ("UPDATE users SET name='x'", "UPDATE"),
        ("INSERT INTO users VALUES (1, 'x')", "INSERT"),
        ("TRUNCATE TABLE users", "TRUNCATE"),
        ("ALTER TABLE users ADD COLUMN x INT", "ALTER"),
        ("CREATE TABLE test (id INT)", "CREATE"),
    ])
    def test_forbidden_operations(self, validator, sql, operation):
        """UT-VAL-004~010: 拒绝写操作"""
        with pytest.raises(SQLValidationError) as exc_info:
            validator.validate(sql)
        assert operation.lower() in str(exc_info.value).lower()

    def test_multi_statement_rejected(self, validator):
        """UT-VAL-013: 拒绝多语句"""
        sql = "SELECT 1; DROP TABLE users;"
        with pytest.raises(SQLValidationError) as exc_info:
            validator.validate(sql)
        assert "multiple statements" in str(exc_info.value).lower()

    def test_cte_query_passes(self, validator):
        """UT-VAL-014: CTE 查询通过"""
        sql = "WITH cte AS (SELECT * FROM users) SELECT * FROM cte"
        result = validator.validate(sql)
        assert result.is_valid is True
```

### 3.4 数据库执行器 (pg_mcp/services/executor.py)

#### 测试套件: TestSQLExecutor

**测试用例:**

| 用例 ID | 测试场景 | 输入 | 期望输出 | 优先级 |
|---------|---------|------|----------|--------|
| UT-EXE-001 | 连接池初始化 | 有效配置 | 连接池创建成功 | P0 |
| UT-EXE-002 | 执行简单查询 | `SELECT 1` | 返回结果集 | P0 |
| UT-EXE-003 | 查询超时处理 | 慢查询 + 超时 | TimeoutError | P0 |
| UT-EXE-004 | 数据库连接失败 | 错误的主机 | DatabaseError | P0 |
| UT-EXE-005 | 只读事务验证 | Mock 连接 | transaction(readonly=True) | P0 |
| UT-EXE-006 | 结果集格式化 | 查询结果 | List[Dict] 格式 | P1 |
| UT-EXE-007 | 空结果集处理 | 无匹配行 | 空列表 | P1 |
| UT-EXE-008 | 连接池关闭 | close() | 所有连接释放 | P1 |
| UT-EXE-009 | 并发查询 | 10 个并发请求 | 全部成功 | P2 |

**实现示例:**

```python
# tests/unit/services/test_executor.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pg_mcp.services.executor import SQLExecutor
from pg_mcp.config.settings import DatabaseConfig
from pg_mcp.exceptions.errors import DatabaseError

class TestSQLExecutor:
    @pytest.fixture
    def db_config(self):
        return DatabaseConfig(
            host="localhost",
            port=5432,
            database="testdb",
            user="testuser",
            password="testpass"
        )

    @pytest.fixture
    async def executor(self, db_config):
        executor = SQLExecutor(db_config)
        yield executor
        await executor.close()

    @pytest.mark.asyncio
    async def test_execute_simple_query(self, executor):
        """UT-EXE-002: 执行简单查询"""
        with patch('asyncpg.create_pool') as mock_pool:
            mock_conn = AsyncMock()
            mock_conn.fetch.return_value = [{"result": 1}]
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

            result = await executor.execute("SELECT 1 as result")
            assert len(result) == 1
            assert result[0]["result"] == 1

    @pytest.mark.asyncio
    async def test_readonly_transaction(self, executor):
        """UT-EXE-005: 只读事务验证"""
        with patch('asyncpg.create_pool') as mock_pool:
            mock_conn = AsyncMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

            await executor.execute("SELECT * FROM users")
            mock_conn.transaction.assert_called_once_with(readonly=True)
```

### 3.5 Schema 发现服务 (pg_mcp/services/schema.py)

#### 测试套件: TestSchemaService

**测试用例:**

| 用例 ID | 测试场景 | 输入 | 期望输出 | 优先级 |
|---------|---------|------|----------|--------|
| UT-SCH-001 | 发现所有表 | 数据库连接 | 表列表 | P0 |
| UT-SCH-002 | 获取表结构 | 表名 | 列信息列表 | P0 |
| UT-SCH-003 | 缓存命中 | 重复请求 | 不查询数据库 | P1 |
| UT-SCH-004 | 缓存过期 | TTL 超时 | 重新查询 | P1 |
| UT-SCH-005 | 批量查询优化 | 多表 | 单次查询 | P1 |
| UT-SCH-006 | 空数据库处理 | 无表 | 空列表 | P2 |
| UT-SCH-007 | 格式化为 Markdown | Schema 对象 | Markdown 字符串 | P1 |

**实现示例:**

```python
# tests/unit/services/test_schema.py
import pytest
from unittest.mock import AsyncMock, patch
from pg_mcp.services.schema import SchemaService
from pg_mcp.services.executor import SQLExecutor

class TestSchemaService:
    @pytest.fixture
    def mock_executor(self):
        executor = AsyncMock(spec=SQLExecutor)
        return executor

    @pytest.fixture
    def schema_service(self, mock_executor):
        return SchemaService(mock_executor, cache_ttl=60)

    @pytest.mark.asyncio
    async def test_discover_tables(self, schema_service, mock_executor):
        """UT-SCH-001: 发现所有表"""
        mock_executor.execute.return_value = [
            {"table_name": "users", "column_name": "id", "data_type": "integer"},
            {"table_name": "users", "column_name": "name", "data_type": "text"},
        ]

        schema = await schema_service.discover()
        assert len(schema.tables) == 1
        assert schema.tables[0].name == "users"
        assert len(schema.tables[0].columns) == 2

    @pytest.mark.asyncio
    async def test_cache_hit(self, schema_service, mock_executor):
        """UT-SCH-003: 缓存命中"""
        mock_executor.execute.return_value = [
            {"table_name": "users", "column_name": "id", "data_type": "integer"}
        ]

        # 第一次调用
        await schema_service.discover()
        # 第二次调用
        await schema_service.discover()

        # 只应该查询一次数据库
        assert mock_executor.execute.call_count == 1
```

### 3.6 LLM 服务 (pg_mcp/services/llm.py)

#### 测试套件: TestLLMService

**测试用例:**

| 用例 ID | 测试场景 | 输入 | 期望输出 | 优先级 |
|---------|---------|------|----------|--------|
| UT-LLM-001 | 成功生成 SQL | 自然语言 + Schema | SQL 字符串 | P0 |
| UT-LLM-002 | API 调用失败重试 | 503 错误 | 重试 3 次 | P0 |
| UT-LLM-003 | 指数退避验证 | 重试间隔 | 1s, 2s, 4s | P1 |
| UT-LLM-004 | 最大重试后失败 | 持续失败 | LLMError | P0 |
| UT-LLM-005 | Prompt 构建 | Schema + 问题 | 包含完整上下文 | P1 |
| UT-LLM-006 | API 超时处理 | 超时 | TimeoutError | P1 |
| UT-LLM-007 | 无效响应处理 | 非 JSON | LLMError | P1 |
| UT-LLM-008 | 空响应处理 | 空字符串 | LLMError | P2 |

**实现示例:**

```python
# tests/unit/services/test_llm.py
import pytest
from unittest.mock import AsyncMock, patch
from httpx import Response, HTTPStatusError
from pg_mcp.services.llm import LLMService
from pg_mcp.config.settings import LLMConfig
from pg_mcp.exceptions.errors import LLMError

class TestLLMService:
    @pytest.fixture
    def llm_config(self):
        return LLMConfig(
            api_key="sk-test",
            model="deepseek-chat",
            base_url="https://api.deepseek.com"
        )

    @pytest.fixture
    def llm_service(self, llm_config):
        return LLMService(llm_config)

    @pytest.mark.asyncio
    async def test_generate_sql_success(self, llm_service):
        """UT-LLM-001: 成功生成 SQL"""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = Response(
                200,
                json={
                    "choices": [{
                        "message": {
                            "content": "SELECT * FROM users WHERE age > 18"
                        }
                    }]
                }
            )

            sql = await llm_service.generate_sql(
                question="查询年龄大于18的用户",
                schema_context="Table: users (id, name, age)"
            )
            assert "SELECT" in sql
            assert "users" in sql

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, llm_service):
        """UT-LLM-002: API 调用失败重试"""
        with patch('httpx.AsyncClient.post') as mock_post:
            # 前两次失败，第三次成功
            mock_post.side_effect = [
                HTTPStatusError("503", request=None, response=Response(503)),
                HTTPStatusError("503", request=None, response=Response(503)),
                Response(200, json={"choices": [{"message": {"content": "SELECT 1"}}]})
            ]

            sql = await llm_service.generate_sql("test", "schema")
            assert mock_post.call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, llm_service):
        """UT-LLM-004: 最大重试后失败"""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.side_effect = HTTPStatusError("503", request=None, response=Response(503))

            with pytest.raises(LLMError) as exc_info:
                await llm_service.generate_sql("test", "schema")
            assert "max retries" in str(exc_info.value).lower()
```

### 3.7 数据模型层 (pg_mcp/models/)

#### 测试套件: TestModels

**测试用例:**

| 用例 ID | 测试场景 | 输入 | 期望输出 | 优先级 |
|---------|---------|------|----------|--------|
| UT-MOD-001 | QueryRequest 验证 | 有效数据 | 模型实例 | P0 |
| UT-MOD-002 | 空问题拒绝 | question="" | ValidationError | P1 |
| UT-MOD-003 | QueryResponse 序列化 | 结果数据 | JSON 字符串 | P1 |
| UT-MOD-004 | ErrorResponse 格式 | 错误信息 | 标准格式 | P1 |
| UT-MOD-005 | SchemaInfo 模型 | 表结构 | 正确嵌套 | P1 |

**实现示例:**

```python
# tests/unit/models/test_request.py
import pytest
from pydantic import ValidationError
from pg_mcp.models.request import QueryRequest

class TestQueryRequest:
    def test_valid_request(self):
        """UT-MOD-001: QueryRequest 验证"""
        req = QueryRequest(question="查询所有用户")
        assert req.question == "查询所有用户"

    def test_empty_question_rejected(self):
        """UT-MOD-002: 空问题拒绝"""
        with pytest.raises(ValidationError):
            QueryRequest(question="")
```

---

## 4. 集成测试计划

### 4.1 数据库集成测试

#### 测试套件: TestDatabaseIntegration

**测试环境:** 使用独立 PostgreSQL 测试实例（本地或 CI service）

**测试用例:**

| 用例 ID | 测试场景 | 前置条件 | 验证点 | 优先级 |
|---------|---------|---------|--------|--------|
| IT-DB-001 | 连接池生命周期 | PostgreSQL 测试实例 | 连接创建/关闭 | P0 |
| IT-DB-002 | 真实查询执行 | 测试数据 | 返回正确结果 | P0 |
| IT-DB-003 | 事务只读验证 | 尝试写操作 | 抛出异常 | P0 |
| IT-DB-004 | 并发查询处理 | 50 个并发请求 | 全部成功 | P1 |
| IT-DB-005 | 连接池耗尽恢复 | 超过最大连接数 | 等待后成功 | P1 |
| IT-DB-006 | 查询超时 | 慢查询 | 超时中断 | P1 |

**实现示例:**

```python
# tests/integration/test_database.py
import pytest
from pg_mcp.services.executor import SQLExecutor
from pydantic import SecretStr
from pg_mcp.config.settings import DatabaseConfig, QueryConfig

@pytest.fixture
async def executor():
    query_config = QueryConfig(timeout_seconds=3, max_rows=100, max_rows_limit=1000)
    config = DatabaseConfig(
        name="test_db",
        host="127.0.0.1",
        port=5433,
        database="test_db",
        username="test_user",
        password=SecretStr("test_pass"),
        is_default=True,
    )
    executor = SQLExecutor(query_config)
    await executor.initialize([config])
    yield executor
    await executor.close()

@pytest.mark.asyncio
async def test_real_query_execution(executor):
    """IT-DB-002: 真实查询执行"""
    # 创建测试数据
    pool = executor.get_pool("test_db")
    async with pool.acquire() as conn:
        await conn.execute("CREATE TABLE test_users (id INT, name TEXT)")
        await conn.execute("INSERT INTO test_users VALUES (1, 'Alice'), (2, 'Bob')")

    # 执行查询
    result = await executor.execute("test_db", "SELECT * FROM test_users ORDER BY id", limit=10)
    assert result.row_count == 2
    assert result.rows[0][1] == "Alice"
```

### 4.2 Schema 发现集成测试

#### 测试套件: TestSchemaIntegration

**测试用例:**

| 用例 ID | 测试场景 | 前置条件 | 验证点 | 优先级 |
|---------|---------|---------|--------|--------|
| IT-SCH-001 | 发现真实表结构 | 多表数据库 | 完整 Schema | P0 |
| IT-SCH-002 | 外键关系识别 | 带外键的表 | 关系信息 | P1 |
| IT-SCH-003 | 索引信息获取 | 带索引的表 | 索引列表 | P2 |
| IT-SCH-004 | 大型数据库性能 | 100+ 表 | < 5s 完成 | P1 |

**实现示例:**

```python
# tests/integration/test_schema.py
import pytest
from pg_mcp.services.schema import SchemaService

@pytest.mark.asyncio
async def test_discover_real_schema(executor):
    """IT-SCH-001: 发现真实表结构"""
    # 创建测试表
    await executor.execute("""
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255) UNIQUE
        )
    """)

    service = SchemaService(executor)
    schema = await service.discover()

    assert len(schema.tables) >= 1
    users_table = next(t for t in schema.tables if t.name == "users")
    assert len(users_table.columns) == 3
    assert any(c.name == "id" for c in users_table.columns)
```

### 4.3 端到端 SQL 生成测试

#### 测试套件: TestE2ESQLGeneration

**测试用例:**

| 用例 ID | 测试场景 | 输入 | 验证点 | 优先级 |
|---------|---------|------|--------|--------|
| IT-E2E-001 | 自然语言到查询 | "查询所有用户" | 生成有效 SQL | P0 |
| IT-E2E-002 | 复杂查询生成 | "统计每个部门的平均工资" | JOIN + GROUP BY | P1 |
| IT-E2E-003 | 生成的 SQL 可执行 | LLM 输出 | 执行成功 | P0 |
| IT-E2E-004 | 安全校验通过 | 生成的 SQL | 无写操作 | P0 |

**实现示例:**

```python
# tests/integration/test_e2e_sql.py
import pytest
from pg_mcp.services.llm import LLMService
from pg_mcp.security.validator import SQLValidator

@pytest.mark.asyncio
@pytest.mark.integration
async def test_nl_to_executable_sql(llm_service, executor, schema_service):
    """IT-E2E-003: 生成的 SQL 可执行"""
    # 获取 Schema
    schema = await schema_service.discover()
    schema_text = schema.to_markdown()

    # 生成 SQL
    sql = await llm_service.generate_sql(
        question="查询所有用户的姓名和邮箱",
        schema_context=schema_text
    )

    # 验证安全性
    validator = SQLValidator()
    validator.validate(sql)

    # 执行查询
    result = await executor.execute(sql)
    assert isinstance(result, list)
```

---

## 5. 端到端测试计划

### 5.1 MCP 协议测试

#### 测试套件: TestMCPProtocol

**测试环境:** 使用 MCP Inspector 或模拟 MCP Client

**测试用例:**

| 用例 ID | 测试场景 | MCP 请求 | 期望响应 | 优先级 |
|---------|---------|---------|----------|--------|
| E2E-MCP-001 | Tool 列表发现 | list_tools | 包含 query_database | P0 |
| E2E-MCP-002 | Tool 调用成功 | call_tool(query_database) | 返回查询结果 | P0 |
| E2E-MCP-003 | 错误响应格式 | 无效 SQL | 标准错误格式 | P0 |
| E2E-MCP-004 | 服务启动/关闭 | 生命周期 | 资源正确释放 | P1 |

**实现示例:**

```python
# tests/e2e/test_mcp_protocol.py
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_tool_discovery():
    """E2E-MCP-001: Tool 列表发现"""
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "pg_mcp"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()

            assert len(tools) > 0
            assert any(t.name == "query_database" for t in tools)

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_query_execution():
    """E2E-MCP-002: Tool 调用成功"""
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "query_database",
                arguments={"question": "查询所有用户"}
            )

            assert result.isError is False
            assert "content" in result
```

### 5.2 完整用户场景测试

#### 测试场景矩阵

| 场景 ID | 用户故事 | 步骤 | 验证点 | 优先级 |
|---------|---------|------|--------|--------|
| E2E-US-001 | 数据分析师查询用户统计 | 1. 连接数据库<br>2. 询问"有多少活跃用户"<br>3. 获取结果 | 返回正确数量 | P0 |
| E2E-US-002 | 开发者探索数据库结构 | 1. 请求 Schema<br>2. 查看表列表 | 显示所有表 | P0 |
| E2E-US-003 | 业务人员生成报表 | 1. 复杂聚合查询<br>2. 多表 JOIN | 正确结果 | P1 |
| E2E-US-004 | 安全测试：尝试删除数据 | 1. 输入"删除所有用户"<br>2. 系统拒绝 | 返回错误 | P0 |

---

## 6. 安全测试计划

### 6.1 SQL 注入测试

#### 测试套件: TestSQLInjection

**测试用例:**

| 用例 ID | 攻击向量 | 输入 | 期望结果 | 优先级 |
|---------|---------|------|----------|--------|
| SEC-INJ-001 | 经典注入 | `' OR '1'='1` | 被拦截 | P0 |
| SEC-INJ-002 | 联合查询注入 | `UNION SELECT * FROM passwords` | 被拦截 | P0 |
| SEC-INJ-003 | 堆叠查询 | `; DROP TABLE users;` | 被拦截 | P0 |
| SEC-INJ-004 | 注释绕过 | `--`, `/**/` | 被拦截 | P0 |
| SEC-INJ-005 | 编码绕过 | URL 编码、十六进制 | 被拦截 | P1 |

**实现示例:**

```python
# tests/security/test_sql_injection.py
import pytest
from pg_mcp.security.validator import SQLValidator
from pg_mcp.exceptions.errors import SQLValidationError

class TestSQLInjection:
    @pytest.fixture
    def validator(self):
        return SQLValidator()

    @pytest.mark.parametrize("malicious_input", [
        "' OR '1'='1",
        "'; DROP TABLE users; --",
        "UNION SELECT * FROM passwords",
        "1; DELETE FROM users WHERE 1=1",
        "admin'--",
        "1' AND 1=1 UNION SELECT NULL, table_name FROM information_schema.tables--",
    ])
    def test_injection_blocked(self, validator, malicious_input):
        """SEC-INJ-001~004: SQL 注入被拦截"""
        with pytest.raises(SQLValidationError):
            validator.validate(f"SELECT * FROM users WHERE name='{malicious_input}'")
```

### 6.2 权限测试

#### 测试套件: TestPermissions

**测试用例:**

| 用例 ID | 测试场景 | 操作 | 期望结果 | 优先级 |
|---------|---------|------|----------|--------|
| SEC-PERM-001 | 只读角色验证 | 尝试 INSERT | 数据库拒绝 | P0 |
| SEC-PERM-002 | 系统表访问 | 查询 pg_shadow | 被拒绝 | P1 |
| SEC-PERM-003 | 跨 Schema 访问 | 访问其他 Schema | 被拒绝 | P1 |

---

## 7. 性能测试计划

### 7.1 响应时间测试

**测试用例:**

| 用例 ID | 测试场景 | 负载 | 目标 | 优先级 |
|---------|---------|------|------|--------|
| PERF-RT-001 | 简单查询响应 | 单请求 | < 2s | P0 |
| PERF-RT-002 | 复杂查询响应 | JOIN + 聚合 | < 5s | P1 |
| PERF-RT-003 | Schema 发现 | 100 表 | < 5s | P1 |
| PERF-RT-004 | LLM 生成 SQL | 单请求 | < 3s | P1 |

### 7.2 并发测试

**测试用例:**

| 用例 ID | 测试场景 | 并发数 | 成功率 | 优先级 |
|---------|---------|--------|--------|--------|
| PERF-CON-001 | 并发查询 | 10 | 100% | P1 |
| PERF-CON-002 | 高并发 | 50 | ≥ 95% | P2 |
| PERF-CON-003 | 连接池压力 | 100 | 无泄漏 | P1 |

**实现示例:**

```python
# tests/performance/test_concurrency.py
import pytest
import asyncio
from pg_mcp.services.executor import SQLExecutor

@pytest.mark.asyncio
@pytest.mark.performance
async def test_concurrent_queries(executor):
    """PERF-CON-001: 并发查询"""
    async def query():
        return await executor.execute("SELECT 1")

    tasks = [query() for _ in range(10)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 验证所有请求成功
    assert all(not isinstance(r, Exception) for r in results)
    assert len(results) == 10
```

---

## 8. 测试执行计划

### 8.1 测试阶段

| 阶段 | 测试类型 | 触发条件 | 通过标准 |
|------|---------|---------|----------|
| 开发阶段 | 单元测试 | 每次代码提交 | 覆盖率 ≥ 85% |
| 集成阶段 | 集成测试 | 每日构建 | 全部通过 |
| 发布前 | E2E + 安全 | PR 合并前 | 全部通过 |
| 发布后 | 性能测试 | 每周 | 满足 NFR |

### 8.2 CI/CD 配置

**GitHub Actions 工作流:**

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit -v --cov=pg_mcp --cov-report=xml
      - uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: testpass
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
    steps:
      - uses: actions/checkout@v3
      - run: pytest tests/integration -v

  security-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: bandit -r pg_mcp/
      - run: pytest tests/security -v
```

### 8.3 测试数据管理

**Fixtures 组织:**

```python
# tests/conftest.py
import pytest
import asyncpg

@pytest.fixture(scope="session")
async def pg_conn():
    """全局 PostgreSQL 连接"""
    conn = await asyncpg.connect(
        host="127.0.0.1",
        port=5433,
        database="test_db",
        user="test_user",
        password="test_pass",
    )
    yield conn
    await conn.close()

@pytest.fixture
async def test_database(pg_conn):
    """测试数据库初始化"""
    await pg_conn.execute("""
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(255),
            age INT
        )
    """)
    await pg_conn.execute("""
        INSERT INTO users (name, email, age) VALUES
        ('Alice', 'alice@example.com', 25),
        ('Bob', 'bob@example.com', 30),
        ('Charlie', 'charlie@example.com', 35)
    """)
    yield pg_conn
    await pg_conn.execute("DROP TABLE users")
```

---

## 9. 测试覆盖率目标

### 9.1 代码覆盖率

| 模块 | 目标覆盖率 | 关键路径 |
|------|-----------|----------|
| config/settings.py | ≥ 90% | 配置验证 |
| security/validator.py | 100% | 所有校验规则 |
| services/executor.py | ≥ 85% | 查询执行 |
| services/schema.py | ≥ 80% | Schema 发现 |
| services/llm.py | ≥ 75% | LLM 调用 |
| server.py | ≥ 70% | Tool 注册 |

### 9.2 功能覆盖率

| PRD 需求 | 测试用例数 | 覆盖率 |
|---------|-----------|--------|
| FR-001 数据库连接 | 8 | 100% |
| FR-002 Schema 发现 | 7 | 100% |
| FR-005 SQL 生成 | 8 | 100% |
| FR-006 SQL 校验 | 20 | 100% |
| FR-007 SQL 执行 | 9 | 100% |
| NFR-004 查询安全 | 15 | 100% |

---

## 10. 缺陷管理

### 10.1 缺陷优先级

| 优先级 | 定义 | 响应时间 |
|--------|------|----------|
| P0 | 阻塞功能、安全漏洞 | 立即修复 |
| P1 | 核心功能异常 | 24 小时内 |
| P2 | 次要功能问题 | 1 周内 |
| P3 | 优化建议 | 下个版本 |

### 10.2 缺陷跟踪

使用 GitHub Issues 跟踪，标签分类：
- `bug`: 功能缺陷
- `security`: 安全问题
- `performance`: 性能问题
- `test-failure`: 测试失败

---

## 11. 测试交付物

### 11.1 文档

- [ ] 测试计划文档（本文档）
- [ ] 测试用例清单
- [ ] 测试报告模板
- [ ] 缺陷报告模板

### 11.2 代码

- [ ] 单元测试套件（tests/unit/）
- [ ] 集成测试套件（tests/integration/）
- [ ] E2E 测试套件（tests/e2e/）
- [ ] 性能测试脚本（tests/performance/）
- [ ] 测试 Fixtures（tests/conftest.py）

### 11.3 报告

- [ ] 代码覆盖率报告
- [ ] 测试执行报告
- [ ] 性能测试报告
- [ ] 安全测试报告

---

## 12. 附录

### 12.1 测试工具安装

```bash
# 安装测试依赖
pip install -e ".[dev]"

# 安装额外工具
pip install bandit locust
```

### 12.2 运行测试命令

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit -v

# 运行集成测试
pytest tests/integration -v --tb=short

# 运行 E2E 测试
pytest tests/e2e -v -m e2e

# 生成覆盖率报告
pytest --cov=pg_mcp --cov-report=html

# 运行安全测试
bandit -r pg_mcp/
pytest tests/security -v

# 运行性能测试
pytest tests/performance -v -m performance
```

### 12.3 测试最佳实践

1. **测试隔离**: 每个测试独立，不依赖执行顺序
2. **清理资源**: 使用 fixture 的 yield 确保资源释放
3. **Mock 外部依赖**: LLM API、数据库连接等使用 Mock
4. **参数化测试**: 使用 `@pytest.mark.parametrize` 减少重复代码
5. **异步测试**: 使用 `@pytest.mark.asyncio` 标记异步测试
6. **测试命名**: 使用描述性名称，如 `test_<功能>_<场景>_<期望>`

### 12.4 修订历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0.0 | 2026-02-24 | 初始版本，覆盖单元/集成/E2E/安全/性能测试 |
