# PostgreSQL MCP Server 开发指南

## 项目概述

PostgreSQL MCP Server 是一个基于 Model Context Protocol 的服务，允许 AI 助手通过自然语言查询 PostgreSQL 数据库。

## 技术栈

| 组件 | 技术选型 | 版本要求 |
|------|----------|----------|
| 语言 | Python | 3.12+ |
| MCP 框架 | FastMCP | latest |
| 数据库驱动 | asyncpg | >=0.29.0 |
| SQL 解析 | SQLGlot | >=23.0.0 |
| 配置管理 | pydantic-settings | >=2.0.0 |
| HTTP 客户端 | httpx | >=0.27.0 |

## 项目结构

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

## 命令

```bash
# 安装依赖
pip install -e ".[dev]"

# 运行服务
python -m pg_mcp

# 运行测试
pytest tests/ -v

# 代码检查
ruff check pg_mcp/
ruff format pg_mcp/

# 类型检查
mypy pg_mcp/
```

## 代码规范

### Python Best Practices

1. **类型注解**: 所有函数必须有完整的类型注解
   ```python
   async def execute(self, db_name: str, sql: str, limit: int = 100) -> QueryResult:
   ```

2. **异步优先**: 全链路使用 async/await
   ```python
   async def get_schema(self, db_name: str) -> SchemaInfo | None:
       return self._cache.get(db_name)
   ```

3. **上下文管理器**: 资源管理使用 async with
   ```python
   async with pool.acquire() as conn:
       rows = await conn.fetch(sql)
   ```

4. **Pydantic 模型**: 数据验证使用 Pydantic
   ```python
   class QueryInput(BaseModel):
       query: str = Field(..., description="自然语言查询描述")
       limit: int = Field(100, ge=1, le=1000)
   ```

### SOLID 原则

1. **单一职责 (SRP)**: 每个类只负责一个功能
   - `SQLValidator`: 只负责 SQL 安全校验
   - `SQLExecutor`: 只负责 SQL 执行
   - `SchemaService`: 只负责 Schema 发现与缓存

2. **开闭原则 (OCP)**: 通过配置扩展，不修改核心代码
   ```python
   class SecurityConfig(BaseSettings):
       blocked_functions: list[str] = ["pg_sleep", "lo_export"]
   ```

3. **依赖倒置 (DIP)**: 依赖抽象而非具体实现
   ```python
   class LLMService:
       def __init__(self, config: DeepSeekConfig, schema_service: SchemaService):
           self.config = config
           self.schema_service = schema_service
   ```

### DRY 原则

1. **配置集中管理**: 所有配置通过 `Settings` 类统一管理
2. **错误处理复用**: 使用统一的 `ErrorResponse` 模型
3. **SQL 查询模板**: Schema 发现 SQL 定义为类常量

### 代码风格

```python
# 使用 dataclass 或 Pydantic 替代字典
@dataclass
class ValidationResult:
    is_safe: bool
    message: str = ""
    detected_issues: list[str] = field(default_factory=list)

# 使用 Enum 替代魔法字符串
class ReturnMode(str, Enum):
    SQL = "sql"
    RESULT = "result"
    BOTH = "both"

# 使用 | 替代 Optional (Python 3.10+)
def get_schema(self, db_name: str) -> SchemaInfo | None:
    pass

# 使用 list/dict 替代 List/Dict (Python 3.9+)
blocked_functions: list[str] = []
```

## 测试规范

### 测试结构

```
tests/
├── conftest.py              # 共享 fixtures
├── unit/
│   ├── test_validator.py    # SQL 校验器测试
│   ├── test_executor.py     # 执行器测试
│   └── test_schema.py       # Schema 服务测试
├── integration/
│   └── test_server.py       # 集成测试
└── fixtures/
    └── schemas.py           # 测试数据
```

### 测试要求

1. **覆盖率**: 核心模块 >=90%
2. **异步测试**: 使用 pytest-asyncio
   ```python
   @pytest.mark.asyncio
   async def test_execute_query(executor):
       result = await executor.execute("test_db", "SELECT 1")
       assert result.row_count == 1
   ```

3. **参数化测试**: 覆盖边界条件
   ```python
   @pytest.mark.parametrize("sql,expected", [
       ("SELECT * FROM users", True),
       ("DELETE FROM users", False),
       ("SELECT pg_sleep(10)", False),
   ])
   def test_sql_validation(validator, sql, expected):
       result = validator.validate(sql)
       assert result.is_safe == expected
   ```

4. **Mock 外部依赖**: LLM API 调用使用 mock
   ```python
   @pytest.fixture
   def mock_deepseek(mocker):
       return mocker.patch("pg_mcp.services.llm.httpx.AsyncClient")
   ```

### 安全测试用例

必须覆盖以下场景:
- INSERT/UPDATE/DELETE/DROP 语句拦截
- 危险函数调用拦截 (pg_sleep, lo_export 等)
- 子查询中的写操作拦截
- CTE 中的非 SELECT 语句拦截
- SQL 注入尝试拦截

## 性能要求

| 指标 | 目标值 |
|------|--------|
| Schema 加载 | < 10s (100 表) |
| SQL 生成 | < 5s (不含 LLM 延迟) |
| SQL 校验 | < 100ms |
| 查询执行 | 遵循配置超时 |

### 性能优化

1. **连接池**: 使用 asyncpg 连接池，避免频繁创建连接
2. **Schema 缓存**: 内存缓存，避免重复查询
3. **并发控制**: LLM API 调用限流

## 安全要求

### 三层防护

1. **LLM Prompt 约束**: System Prompt 明确禁止非 SELECT
2. **SQLGlot AST 校验**: 语法级别安全检查
3. **数据库层约束**: 只读角色 + `default_transaction_read_only=on`

### 敏感信息处理

- 密码使用 `SecretStr` 类型
- 日志中不记录完整查询结果
- API Key 通过环境变量注入

## 错误处理

使用统一的错误码:

| 错误码 | 场景 |
|--------|------|
| `DB_NOT_FOUND` | 数据库未配置 |
| `SCHEMA_NOT_READY` | Schema 缓存未就绪 |
| `SQL_GENERATION_ERROR` | LLM 生成失败 |
| `SECURITY_VIOLATION` | 安全校验失败 |
| `QUERY_TIMEOUT` | 查询超时 |
| `QUERY_EXECUTION_ERROR` | SQL 执行错误 |

## 日志规范

```python
import structlog

logger = structlog.get_logger()

# 结构化日志
logger.info(
    "query_executed",
    database=db_name,
    execution_time_ms=elapsed,
    row_count=len(rows),
)
```

## 配置示例

```bash
# .env
DEEPSEEK_API_KEY=sk-xxx
DB_PASSWORD=your_password
PG_MCP_LOG_LEVEL=INFO
```

## Git 提交规范

```
feat: 添加 SQL 安全校验功能
fix: 修复连接池泄漏问题
docs: 更新 API 文档
test: 添加 validator 单元测试
refactor: 重构 Schema 缓存逻辑
perf: 优化查询执行性能
```

## 依赖管理

使用 pyproject.toml 管理依赖:

```toml
[project]
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=0.1.0",
    "asyncpg>=0.29.0",
    "sqlglot>=23.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.3.0",
    "mypy>=1.8.0",
]
```
