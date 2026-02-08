# Data Model: 数据库查询工具

**Feature**: `D:/GithubCode/bootcamp-ai-program-learn/specs/001-db-query-tool/spec.md`  
**Date**: 2026-02-08

## Entity: DbConnection

**Purpose**: 存储用户配置的数据库连接信息（仅 PostgreSQL）与最近连接状态。

**Fields**:

- `name` (string, required): 连接唯一名称，作为主键路径参数 `/{name}`。
- `url` (string, required, write-only in API): PostgreSQL DSN，例如 `postgres://user:pass@host:5432/db`。
- `dialect` (enum, required): 固定为 `postgres`。
- `isReachable` (boolean, required): 最近一次探活是否成功。
- `lastCheckedAt` (datetime, nullable): 最近一次连接校验时间。
- `createdAt` (datetime, required)
- `updatedAt` (datetime, required)

**Validation Rules**:

- `name`: `^[a-zA-Z0-9_-]{1,64}$`。
- `url`: 必须可被 PostgreSQL 驱动识别；仅允许 PostgreSQL scheme。
- 同名连接写入遵循“幂等 upsert”：`PUT /dbs/{name}` 覆盖 `url` 与元数据更新时间戳。

**State Transitions**:

- `new -> reachable`：连接成功并可读取元数据。
- `new -> unreachable`：连接失败。
- `reachable -> staleMetadata`：元数据过期或目标库结构变更。
- `staleMetadata -> reachable`：刷新元数据成功。

## Entity: SchemaMetadata

**Purpose**: 缓存目标库表/视图/列信息，供展示与 NL2SQL 上下文复用。

**Fields**:

- `connectionName` (string, required, FK -> DbConnection.name)
- `metadataJson` (object, required): 规范化 JSON，包含 tables/views/columns。
- `metadataHash` (string, required): 元数据摘要，用于变更检测。
- `sourceCapturedAt` (datetime, required): 从 PostgreSQL 抓取完成时间。
- `normalizedAt` (datetime, required): LLM JSON 归一化完成时间。
- `version` (integer, required): 每次刷新递增。

**Validation Rules**:

- `metadataJson` 顶层结构必须包含 `tables` 和 `views` 数组。
- 每个表/视图字段必须包含 `name` 与 `columns`。
- `columns[*].name` 非空，`columns[*].dataType` 非空。

## Entity: QueryRequest

**Purpose**: 表示用户提交的查询请求（原生 SQL 或自然语言）。

**Fields**:

- `connectionName` (string, required)
- `mode` (enum, required): `sql` | `natural`
- `sql` (string, conditional): `mode=sql` 时必填。
- `prompt` (string, conditional): `mode=natural` 时必填。
- `appliedLimit` (integer, nullable): 规范化后实际 limit，默认 `1000`。

**Validation Rules**:

- `sql` 必须被 `sqlglot` 成功解析。
- 仅允许单语句 `SELECT`；拒绝 DDL/DML/多语句。
- 无 `LIMIT` 时自动注入 `LIMIT 1000`。

## Entity: QueryResult

**Purpose**: 返回可前端表格渲染的结构化查询结果。

**Fields**:

- `connectionName` (string, required)
- `executedSql` (string, required): 最终执行 SQL（含自动注入 limit）。
- `columns` (array[string], required)
- `rows` (array[array[json]], required)
- `rowCount` (integer, required)
- `durationMs` (integer, required)
- `truncated` (boolean, required): 是否触发结果截断。

**Validation Rules**:

- `rowCount >= 0`。
- `durationMs >= 0`。
- `len(rows) <= appliedLimit`。

## Entity: ApiError

**Purpose**: 统一错误响应模型。

**Fields**:

- `code` (string, required): 机器可读错误码，如 `invalidSql`、`connectionFailed`。
- `message` (string, required): 人类可读错误描述。
- `details` (object, optional): 附加上下文。
- `requestId` (string, optional): 便于追踪。

**Validation Rules**:

- 全字段对外响应保持 camelCase。

## Relationships

- `DbConnection (1) -> (N) SchemaMetadata`（按版本记录刷新历史，可按最新版本读取）
- `DbConnection (1) -> (N) QueryRequest`（可选审计，不作为当前强制持久化）
- `QueryRequest (1) -> (1) QueryResult | ApiError`

## Derived Pydantic Models (Implementation Mapping)

- `PutDbRequest`, `DbConnectionSummary`, `DbConnectionDetail`
- `NaturalQueryRequest`, `SqlQueryRequest`
- `QueryResponse`, `NaturalQueryResponse`
- `ErrorResponse`

上述模型在后端实现中应统一启用别名生成器，内部 snake_case，外部输出 camelCase。
