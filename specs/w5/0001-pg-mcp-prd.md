# PostgreSQL MCP Server 产品需求文档 (PRD)

> 版本: 1.0.0
> 创建日期: 2026-02-23
> 状态: 草稿

---

## 1. 概述

### 1.1 项目背景

随着 AI 辅助开发工具的普及，开发者需要一种便捷的方式来通过自然语言与数据库进行交互。Model Context Protocol (MCP) 作为一种标准化的协议，允许 AI 助手与外部工具和数据源进行通信。本项目旨在构建一个基于 MCP 协议的 PostgreSQL 服务器，使用户能够通过自然语言描述查询需求，自动生成并执行 SQL 查询。

### 1.2 项目目标

构建一个 Python 实现的 MCP Server，具备以下核心能力：

1. **自然语言转 SQL**：接收用户的自然语言查询描述，生成对应的 SQL 语句
2. **智能 Schema 感知**：启动时自动发现并缓存数据库结构信息
3. **安全查询控制**：仅允许执行只读查询语句，防止数据篡改
4. **结果验证**：通过 AI 验证查询结果的有效性和相关性
5. **灵活输出**：支持返回 SQL 语句或查询结果两种模式

### 1.3 目标用户

- 数据分析师：需要快速查询数据但不熟悉 SQL 语法
- 开发人员：希望通过 AI 助手加速数据库查询开发
- 产品经理：需要自助获取数据进行决策分析

### 1.4 范围定义

**v1 版本范围内 (In Scope)**：
- 单数据库自然语言查询
- 只读 SELECT 查询
- Schema 自动发现与缓存
- SQL 安全校验
- 基础结果验证

**v1 版本范围外 (Out of Scope)**：
- 写操作（INSERT/UPDATE/DELETE）
- 跨库联邦查询
- 查询结果缓存
- BI 图表输出
- 多租户隔离
- 查询历史持久化

---

## 2. 功能需求

### 2.1 MCP Server 核心功能

#### 2.1.1 服务启动与初始化

**FR-001: 数据库连接配置**

| 属性 | 描述 |
|------|------|
| 优先级 | P0 (必须) |
| 描述 | 服务启动时读取配置文件，获取可访问的数据库连接信息 |

验收标准：
- 支持通过配置文件 (YAML/JSON/ENV) 配置多个数据库连接
- 配置项包括：host, port, database, username, password, ssl_mode
- 支持连接字符串格式配置
- 敏感信息（密码）支持环境变量引用
- 配置验证失败时提供清晰的错误提示

**FR-002: Schema 自动发现与缓存**

| 属性 | 描述 |
|------|------|
| 优先级 | P0 (必须) |
| 描述 | 启动时自动扫描并缓存所有配置数据库的 Schema 信息 |

验收标准：
- 自动发现以下数据库对象：
  - Tables（表）：表名、列名、数据类型、约束、注释
  - Views（视图）：视图名、列定义、底层查询
  - Indexes（索引）：索引名、索引类型、关联列
  - Types（自定义类型）：枚举类型、复合类型
  - Functions（函数）：函数签名（可选）
- Schema 信息缓存在内存中，支持按需刷新
- 记录 Schema 发现的时间戳
- 支持排除特定 schema（如 pg_catalog, information_schema）

**FR-003: Schema 缓存刷新**

| 属性 | 描述 |
|------|------|
| 优先级 | P1 (重要) |
| 描述 | 提供手动刷新 Schema 缓存的能力 |

验收标准：
- 提供 MCP Tool 用于手动触发 Schema 刷新
- 支持刷新单个数据库或全部数据库
- 刷新过程不阻塞正常查询服务
- 返回刷新结果（成功/失败、耗时、变更摘要）

#### 2.1.2 自然语言查询处理

**FR-004: 自然语言输入解析**

| 属性 | 描述 |
|------|------|
| 优先级 | P0 (必须) |
| 描述 | 接收用户的自然语言查询描述，解析查询意图 |

验收标准：
- 支持中文和英文自然语言输入
- 用户可指定目标数据库（若未指定，使用默认数据库）
- 用户可指定返回模式：仅 SQL / 仅结果 / SQL + 结果
- 支持查询条件、排序、分组、聚合等常见查询需求描述
- 支持多表关联查询的自然语言描述

**FR-005: SQL 生成（DeepSeek 集成）**

| 属性 | 描述 |
|------|------|
| 优先级 | P0 (必须) |
| 描述 | 调用 DeepSeek 大模型，基于 Schema 信息和用户输入生成 SQL |

验收标准：
- 集成 DeepSeek API 进行 SQL 生成
- Prompt 包含：
  - 目标数据库的完整 Schema 信息
  - 用户的自然语言查询描述
  - SQL 生成规范和约束（只读、PostgreSQL 语法）
- 生成的 SQL 符合 PostgreSQL 语法规范
- 支持配置 DeepSeek 模型参数（model, temperature 等）
- API 调用失败时有重试机制和降级策略

**FR-006: SQL 安全校验**

| 属性 | 描述 |
|------|------|
| 优先级 | P0 (必须) |
| 描述 | 校验生成的 SQL，确保只包含只读查询语句 |

验收标准：
- 允许的语句类型：SELECT
- 禁止的语句类型：
  - INSERT, UPDATE, DELETE, TRUNCATE
  - CREATE, ALTER, DROP
  - GRANT, REVOKE
  - COPY, EXECUTE
  - 任何 DDL/DML 操作
- 禁止危险函数调用（如 pg_sleep, lo_export 等）
- 禁止子查询中的写操作
- 校验失败时返回明确的拒绝原因
- 使用 SQL 解析器进行语法级别校验，而非简单字符串匹配

**FR-007: SQL 执行与结果获取**

| 属性 | 描述 |
|------|------|
| 优先级 | P0 (必须) |
| 描述 | 执行通过校验的 SQL 并获取查询结果 |

验收标准：
- 使用只读事务执行查询
- 设置查询超时限制（可配置，默认 30 秒）
- 设置结果集大小限制（可配置，默认 100 行，最大 1000 行）
- 正确处理各种 PostgreSQL 数据类型的序列化
- 查询执行失败时返回友好的错误信息

**FR-008: 结果有效性验证（OpenAI 集成）**

| 属性 | 描述 |
|------|------|
| 优先级 | P1 (重要) |
| 描述 | 调用 OpenAI 验证查询结果是否符合用户意图 |

验收标准：
- 集成 OpenAI API 进行结果验证
- 验证输入包含：
  - 用户原始自然语言查询
  - 生成的 SQL 语句
  - 查询结果样本（前 N 行）
- 验证输出：
  - 置信度评分（0-100）
  - 验证结论（通过/存疑/失败）
  - 问题描述（如有）
  - 改进建议（如有）
- 验证失败时可选择：
  - 返回警告但仍提供结果
  - 拒绝返回并提示用户重新描述
- 支持配置是否启用结果验证（可选功能）
- 支持配置验证阈值

#### 2.1.3 MCP 协议实现

**FR-009: MCP Tools 定义**

| 属性 | 描述 |
|------|------|
| 优先级 | P0 (必须) |
| 描述 | 实现符合 MCP 协议的 Tools |

需要实现的 Tools：

1. **query_database**
   - 描述：通过自然语言查询数据库
   - 参数：
     - `query` (string, required): 自然语言查询描述
     - `database` (string, optional): 目标数据库名称
     - `return_mode` (enum, optional): "sql" | "result" | "both"，默认 "both"
     - `limit` (integer, optional): 结果行数限制，默认 100
   - 返回：SQL 语句和/或查询结果

> **注意**：v1 版本仅实现 `query_database` 核心功能，其他辅助 Tools（如 list_databases、get_schema、refresh_schema、validate_sql）作为 v2 扩展功能

---

## 3. 非功能需求

### 3.1 性能需求

**NFR-001: 响应时间**
- Schema 缓存加载：单个数据库 < 10 秒（100 表规模）
- 自然语言转 SQL：< 5 秒（不含 LLM API 延迟）
- SQL 执行：遵循配置的超时限制
- 结果验证：< 3 秒（不含 LLM API 延迟）

**NFR-002: 并发处理**
- 支持同时处理多个查询请求
- 数据库连接池管理，避免连接耗尽
- LLM API 调用支持并发限流

### 3.2 安全需求

**NFR-003: 数据安全**
- 数据库凭证加密存储或通过环境变量注入
- 禁止在日志中记录敏感信息（密码、完整查询结果）
- 支持 SSL/TLS 数据库连接
- API Key（DeepSeek/OpenAI）安全管理

**NFR-004: 查询安全**
- 严格的只读查询限制（见 FR-006）
- SQL 注入防护：使用参数化执行，禁止拼接动态标识符
- 查询资源限制（超时、结果集大小）
- 数据库侧强约束：使用只读角色，设置 `default_transaction_read_only=on`

**NFR-005: 审计日志**
- 记录所有查询请求（用户输入、生成 SQL、执行结果摘要）
- 记录安全校验失败的尝试
- 日志支持结构化输出（JSON 格式）
- 日志保留周期：默认 30 天，敏感字段脱敏处理

**NFR-005a: LLM 数据安全**
- 发送给 LLM 的 Schema 信息需脱敏处理（移除敏感列注释）
- 查询结果样本限制为前 5 行，敏感列自动屏蔽
- 支持配置"不出域模式"：禁止将任何数据发送给外部 LLM

**NFR-005b: Prompt 注入防护**
- 用户输入与系统提示严格分区
- 对用户输入进行可疑指令检测
- SQL 生成前后双重校验
- 支持日志级别配置

### 3.3 可靠性需求

**NFR-006: 错误处理**
- 数据库连接失败自动重试
- LLM API 调用失败降级处理
- 优雅的错误信息返回，不暴露内部实现细节
- 服务健康检查端点

**NFR-007: 可用性**
- 单个数据库不可用不影响其他数据库查询
- Schema 缓存刷新失败不影响现有缓存使用
- 支持优雅关闭（处理完当前请求后退出）

### 3.4 可维护性需求

**NFR-008: 配置管理**
- 支持配置文件热重载（可选）
- 配置项有合理的默认值
- 配置验证和错误提示

**NFR-009: 可观测性**
- 结构化日志输出
- 关键指标暴露（请求数、成功率、延迟等）
- 支持 OpenTelemetry 追踪（可选）

---

## 4. 技术约束

### 4.1 技术栈要求

| 组件 | 要求 |
|------|------|
| 编程语言 | Python 3.12+ |
| MCP SDK | 官方 Python MCP SDK |
| 数据库驱动 | asyncpg 或 psycopg3 |
| SQL 解析 | pglast（PostgreSQL 语义 AST，安全校验必需） |
| HTTP 客户端 | httpx 或 aiohttp |
| 配置管理 | pydantic-settings |

### 4.2 外部依赖

| 服务 | 用途 | 必需性 |
|------|------|--------|
| PostgreSQL | 目标数据库 | 必需 |
| DeepSeek API | SQL 生成 | 必需 |
| OpenAI API | 结果验证 | 可选 |

### 4.3 部署要求

- 支持本地运行（默认 `stdio`，可选 `streamable-http`）
- 支持作为 MCP Server 被 Claude Desktop 等客户端调用

---

## 5. 用户交互流程

### 5.1 主流程：自然语言查询

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           用户自然语言查询流程                                │
└─────────────────────────────────────────────────────────────────────────────┘

用户                    MCP Client              MCP Server              外部服务
 │                          │                       │                       │
 │  1. 输入自然语言查询      │                       │                       │
 │─────────────────────────>│                       │                       │
 │                          │  2. 调用 query_database│                       │
 │                          │──────────────────────>│                       │
 │                          │                       │  3. 调用 DeepSeek     │
 │                          │                       │      生成 SQL         │
 │                          │                       │──────────────────────>│
 │                          │                       │<──────────────────────│
 │                          │                       │  4. SQL 安全校验      │
 │                          │                       │──────┐                │
 │                          │                       │<─────┘                │
 │                          │                       │  5. 执行 SQL 查询     │
 │                          │                       │──────┐                │
 │                          │                       │<─────┘                │
 │                          │                       │  6. 调用 OpenAI       │
 │                          │                       │      验证结果         │
 │                          │                       │──────────────────────>│
 │                          │                       │<──────────────────────│
 │                          │  7. 返回结果          │                       │
 │                          │<──────────────────────│                       │
 │  8. 展示结果             │                       │                       │
 │<─────────────────────────│                       │                       │
 │                          │                       │                       │
```

### 5.2 示例交互

**示例 1：简单查询**

```
用户输入: "查询所有用户的姓名和邮箱"
目标数据库: default_db
返回模式: both

生成 SQL:
SELECT name, email FROM users;

查询结果:
| name     | email              |
|----------|-------------------|
| 张三     | zhangsan@test.com |
| 李四     | lisi@test.com     |
...

验证结果: 通过 (置信度: 95)
```

**示例 2：复杂查询**

```
用户输入: "统计每个部门的员工数量，按数量降序排列，只显示员工数超过5人的部门"
目标数据库: hr_db
返回模式: sql

生成 SQL:
SELECT
    d.department_name,
    COUNT(e.employee_id) as employee_count
FROM departments d
LEFT JOIN employees e ON d.department_id = e.department_id
GROUP BY d.department_id, d.department_name
HAVING COUNT(e.employee_id) > 5
ORDER BY employee_count DESC;
```

**示例 3：安全拦截**

```
用户输入: "删除所有过期的订单记录"
目标数据库: order_db

响应:
{
  "error": "SECURITY_VIOLATION",
  "message": "检测到非只读操作（DELETE），本服务仅支持查询操作。",
  "suggestion": "如需查看过期订单，请尝试：'查询所有过期的订单记录'"
}
```

---

## 6. 配置规范

### 6.1 配置文件结构

```yaml
# config.yaml 示例

server:
  name: "pg-mcp-server"
  version: "1.0.0"
  log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR

databases:
  - name: "default_db"
    host: "localhost"
    port: 5432
    database: "myapp"
    username: "readonly_user"
    password: "${DB_PASSWORD}"  # 环境变量引用
    ssl_mode: "prefer"
    default: true

  - name: "analytics_db"
    connection_string: "${ANALYTICS_DB_URL}"

schema_discovery:
  excluded_schemas:
    - "pg_catalog"
    - "information_schema"
    - "pg_toast"
  include_functions: false
  cache_ttl_minutes: 60

llm:
  deepseek:
    api_key: "${DEEPSEEK_API_KEY}"
    model: "deepseek-chat"
    temperature: 0.1
    max_tokens: 2000
    timeout_seconds: 30

  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4o-mini"
    enabled: true  # 结果验证开关
    confidence_threshold: 70

query:
  timeout_seconds: 30
  max_rows: 100  # 默认 100，最大 1000
  default_return_mode: "both"  # sql, result, both

security:
  allowed_statements:
    - "SELECT"
  blocked_functions:
    - "pg_sleep"
    - "lo_export"
    - "lo_import"
    - "pg_read_file"
    - "pg_write_file"
```

### 6.2 环境变量

| 变量名 | 描述 | 必需 |
|--------|------|------|
| `DB_PASSWORD` | 数据库密码 | 是 |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | 是 |
| `OPENAI_API_KEY` | OpenAI API 密钥 | 否（如启用验证则必需） |
| `PG_MCP_CONFIG` | 配置文件路径 | 否（默认 ./config.yaml） |
| `PG_MCP_LOG_LEVEL` | 日志级别覆盖 | 否 |

---

## 7. 错误处理规范

### 7.1 错误码定义

| 错误码 | 名称 | 描述 | HTTP 等效 |
|--------|------|------|-----------|
| `DB_CONNECTION_ERROR` | 数据库连接错误 | 无法连接到目标数据库 | 503 |
| `DB_NOT_FOUND` | 数据库不存在 | 指定的数据库未配置 | 404 |
| `SCHEMA_NOT_READY` | Schema 未就绪 | Schema 缓存尚未加载完成 | 503 |
| `SQL_GENERATION_ERROR` | SQL 生成失败 | DeepSeek API 调用失败或返回无效 SQL | 500 |
| `SECURITY_VIOLATION` | 安全校验失败 | SQL 包含非只读操作 | 403 |
| `QUERY_TIMEOUT` | 查询超时 | SQL 执行超过时间限制 | 504 |
| `QUERY_EXECUTION_ERROR` | 查询执行错误 | SQL 语法错误或运行时错误 | 400 |
| `VALIDATION_ERROR` | 验证失败 | OpenAI 结果验证未通过 | 422 |
| `VALIDATION_SKIPPED` | 验证跳过 | OpenAI API 不可用，跳过验证 | 200 (警告) |
| `RATE_LIMIT_EXCEEDED` | 请求过于频繁 | 超过 API 调用限制 | 429 |
| `INVALID_INPUT` | 输入无效 | 用户输入格式或内容无效 | 400 |

### 7.2 错误响应格式

```json
{
  "success": false,
  "error": {
    "code": "SECURITY_VIOLATION",
    "message": "检测到非只读操作，本服务仅支持 SELECT 查询",
    "details": {
      "detected_operation": "DELETE",
      "sql_fragment": "DELETE FROM users..."
    },
    "suggestion": "请重新描述您的查询需求，仅支持数据查询操作"
  },
  "request_id": "req_abc123",
  "timestamp": "2026-02-23T10:30:00Z"
}
```

---

## 8. 成功响应格式

### 8.1 查询结果响应

```json
{
  "success": true,
  "data": {
    "sql": "SELECT name, email FROM users WHERE status = 'active' LIMIT 100;",
    "result": {
      "columns": ["name", "email"],
      "rows": [
        ["张三", "zhangsan@test.com"],
        ["李四", "lisi@test.com"]
      ],
      "row_count": 2,
      "truncated": false
    },
    "validation": {
      "status": "passed",
      "confidence": 92,
      "message": "查询结果与用户意图匹配"
    },
    "metadata": {
      "database": "default_db",
      "execution_time_ms": 45,
      "generated_at": "2026-02-23T10:30:00Z"
    }
  },
  "request_id": "req_xyz789"
}
```

### 8.2 Schema 信息响应

```json
{
  "success": true,
  "data": {
    "database": "default_db",
    "tables": [
      {
        "name": "users",
        "schema": "public",
        "columns": [
          {
            "name": "id",
            "type": "integer",
            "nullable": false,
            "primary_key": true,
            "comment": "用户ID"
          },
          {
            "name": "name",
            "type": "varchar(100)",
            "nullable": false,
            "comment": "用户姓名"
          }
        ],
        "indexes": [
          {
            "name": "users_pkey",
            "columns": ["id"],
            "unique": true
          }
        ],
        "comment": "用户信息表"
      }
    ],
    "cached_at": "2026-02-23T09:00:00Z"
  }
}
```

---

## 9. 验收标准总览

### 9.1 功能验收

| 编号 | 验收项 | 验收标准 |
|------|--------|----------|
| AC-01 | 服务启动 | 服务能正常启动并加载所有配置的数据库 Schema |
| AC-02 | 自然语言查询 | 能正确理解中英文自然语言并生成有效 SQL |
| AC-03 | 安全校验 | 测试集 100% 拦截非 SELECT 语句，线上误放行率 < 0.01% |
| AC-04 | 查询执行 | 能正确执行 SQL 并返回格式化结果 |
| AC-05 | 结果验证 | （启用验证时）OpenAI 验证能识别明显不匹配的结果 |
| AC-06 | MCP 协议 | query_database Tool 符合 MCP 协议规范 |
| AC-07 | 错误处理 | 所有错误场景返回规范的错误响应 |

### 9.2 非功能验收

| 编号 | 验收项 | 验收标准 |
|------|--------|----------|
| AC-08 | 性能 | Schema 加载 < 10s，查询响应 < 配置超时 |
| AC-09 | 安全 | 无敏感信息泄露，凭证安全存储 |
| AC-10 | 可靠性 | 单点故障不影响整体服务 |
| AC-11 | 日志 | 关键操作有完整审计日志 |

---

## 10. 术语表

| 术语 | 定义 |
|------|------|
| MCP | Model Context Protocol，AI 模型与外部工具通信的标准协议 |
| Schema | 数据库结构信息，包括表、列、索引等定义 |
| Tool | MCP 协议中定义的可调用功能单元 |
| Resource | MCP 协议中定义的可访问数据资源 |
| DeepSeek | 深度求索，提供大语言模型 API 服务 |
| OpenAI | 提供 GPT 系列大语言模型 API 服务 |

---

## 11. 附录

### 11.1 参考资料

- [MCP 协议规范](https://modelcontextprotocol.io/)
- [DeepSeek API 文档](https://platform.deepseek.com/docs)
- [OpenAI API 文档](https://platform.openai.com/docs)
- [PostgreSQL 系统目录](https://www.postgresql.org/docs/current/catalogs.html)

### 11.2 修订历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| 1.0.0 | 2026-02-23 | - | 初始版本 |

---

## 12. 待确认事项

以下事项需要在设计阶段进一步确认：

1. **LLM 选择**：DeepSeek 用于 SQL 生成，OpenAI 用于结果验证，是否需要支持其他 LLM 提供商？
2. **限流策略**：是否需要对单用户/单数据库的查询频率进行限制？
3. **Prompt 模板**：SQL 生成的 Prompt 是否需要支持自定义？
4. **结果格式**：除 JSON 外是否需要支持 CSV、Markdown 等格式输出？

> **已明确为 v2 范围**：多租户隔离、查询历史持久化、查询结果缓存（见 1.4 范围定义）

---

## 13. Codex Review 反馈摘要

本文档经过 Codex 自动化评审，主要改进点：

- **已修复**：
  - 添加范围定义（In Scope / Out of Scope）
  - 统一默认行数限制为 100（最大 1000）
  - 强制使用 pglast 进行 SQL 安全校验
  - 精简 MCP Tools 为仅 query_database
  - 增强安全需求（LLM 数据安全、Prompt 注入防护）
  - 修正验收标准表述

- **待后续版本处理**：
  - 完整的访问控制模型（认证/授权）
  - 端到端 SLA 指标定义
  - 详细测试计划与基准数据集
