# Feature Specification: 数据库查询工具

**Feature Branch**: `001-db-query-tool`  
**Created**: 2026-02-07  
**Status**: Draft  
**Input**: User description: "{ 这是一个数据库查询工具，用户可以添加一个 db url, 系统会连接到数据库，获取数据库的 metadata，然后将数据库中的 table 和 view 的 信息展示出来，然后用户可以自己输入 sql 查询，也可以通过自然语言来生成 sql 查询。 基本想法: - 数据库连接字符串和数据库的 metadata 都会存储到 sqlite 数据库中。我们可以根据 postgres 的功能来查询系统中的表格和视图的信息，然后用 LLM 来将这些信息转换成 json 格式，然后存储到 sqlite 数据库中。这个信息可以复用。 - 当用户使用 LLM 来生成 sql 查询时，我们可以把系统中的表和视图的信息作为 context 传递给 LLM，然后 LLM 会根据这些信息来生成 sql 查询。 - 任何输入的 sql 语句，都需要经过 sqlparser 解析，确保语法正确，并且仅包含 select 语句。如果语法不正确，需要给出错误信息。 - 如果查询不包含 limit 子句，则默认添加 limit 1000 子句。 - 输出格式是 json， 前端将其组织成表格，并显示出来。 }"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 连接数据库并查看元数据 (Priority: P1)

用户提供数据库连接信息，系统验证可用性并展示该库的表与视图信息，便于后续查询。
系统将连接信息与元数据保存并复用；元数据会通过 LLM 转换为 JSON 以便统一存储。

**Why this priority**: 这是所有查询与探索的前置条件，是最小可用能力。

**Independent Test**: 提交有效连接后能看到表/视图列表；提交无效连接会得到错误提示且不保存。

**Acceptance Scenarios**:

1. **Given** 用户尚未配置连接，**When** 提交有效连接信息，**Then** 系统保存连接与元数据（JSON）并展示表与视图列表  
2. **Given** 连接信息无效或不可达，**When** 用户提交连接，**Then** 系统提示错误且不保存连接

---

### User Story 2 - 执行只读 SQL 查询 (Priority: P2)

用户选择数据库连接，输入 SQL 进行只读查询并查看结果。
系统在执行前解析 SQL，确保语法正确且只包含 select。

**Why this priority**: 这是核心价值输出，用户需要能直接查询数据。

**Independent Test**: 输入合法只读查询即可看到表格结果；非法或非只读查询会被拒绝。

**Acceptance Scenarios**:

1. **Given** 已有连接与可用元数据，**When** 用户提交不包含 limit 的只读查询，**Then** 系统自动加默认限制 1000 并返回结果  
2. **Given** 用户提交非只读或语法错误的查询，**When** 执行，**Then** 系统返回清晰错误提示且不执行  
3. **Given** 查询执行成功，**When** 返回结果，**Then** 系统以 JSON 输出供前端渲染表格

---

### User Story 3 - 自然语言生成查询 (Priority: P3)

用户用自然语言描述需求，系统生成 SQL 供用户预览与执行。
系统将已保存的表与视图信息作为上下文提供给生成流程。

**Why this priority**: 降低使用门槛，提升非技术用户的查询效率。

**Independent Test**: 输入自然语言后得到可编辑的 SQL；确认后可执行并展示结果。

**Acceptance Scenarios**:

1. **Given** 已有连接与元数据，**When** 用户输入自然语言需求，**Then** 系统生成 SQL 预览  
2. **Given** 用户确认生成的 SQL，**When** 执行，**Then** 系统返回查询结果  
3. **Given** 生成失败或不可信，**When** 系统提示，**Then** 用户可转为手动输入查询

---

### Edge Cases

- 数据库为空或没有可见表/视图时的提示与空状态展示  
- 元数据已过期导致查询失败时，是否提示刷新并重试  
- 查询结果为空、结果行数超过默认限制、或字段名重复  
- 执行期间网络中断或连接失效  
- 同一连接被重复添加时的去重/覆盖策略

### Assumptions & Dependencies

- 当前范围仅支持 PostgreSQL 的元数据与查询能力，跨数据库兼容不在本次范围内  
- 用户能提供有效且具备只读权限的连接信息  
- 元数据会被缓存并在必要时刷新  
- 自然语言查询生成依赖可用的 LLM 服务  
- 元数据 JSON 转换依赖可用的 LLM 服务  
- 连接字符串与元数据存储在本地 SQLite 中以便复用

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统必须允许用户添加数据库连接信息  
- **FR-002**: 系统必须验证连接有效性并在失败时给出错误提示  
- **FR-003**: 系统必须存储连接信息与元数据供复用（本地 SQLite）  
- **FR-004**: 系统必须展示表与视图的基础信息（名称、字段）  
- **FR-005**: 系统必须允许用户刷新元数据  
- **FR-006**: 用户必须能够提交只读 SQL 查询并查看结果  
- **FR-007**: 系统必须通过 SQL 解析器校验语法且仅允许 select 查询  
- **FR-008**: 若查询未包含限制，系统必须默认添加 limit 1000  
- **FR-009**: 系统必须以 JSON 输出列名与行数据供前端展示为表格  
- **FR-010**: 系统必须支持自然语言生成 SQL，并提供可编辑预览  
- **FR-011**: 系统不得要求登录或认证即可使用  
- **FR-012**: 系统必须对连接、生成、执行的失败场景提供清晰错误信息
- **FR-013**: 系统必须基于 PostgreSQL 能力读取表与视图元数据  
- **FR-014**: 系统必须将元数据转换为 JSON 并持久化以便复用  
- **FR-015**: 系统必须在自然语言生成 SQL 时提供表与视图上下文
- **FR-016**: 系统必须使用 LLM 将元数据转换为 JSON 后再持久化

### Constitution Constraints *(mandatory)*

- **CC-001**: Backend implementation MUST use Python and follow Ergonomic Python style
- **CC-002**: Frontend MUST use TypeScript with strict typing enabled
- **CC-003**: Backend data models MUST be defined and validated with Pydantic
- **CC-004**: All backend JSON responses MUST use camelCase keys
- **CC-005**: The system MUST NOT implement authentication/authorization

### Key Entities *(include if feature involves data)*

- **Connection**: 用户提供的连接信息与连接状态  
- **SchemaMetadata**: 该连接对应的表、视图与字段信息  
- **QueryRequest**: 用户提交的 SQL 或自然语言请求  
- **QueryResult**: 查询结果的数据集与列信息  
- **QueryError**: 连接/校验/执行失败时的错误信息

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 90% 的用户能在 30 秒内完成连接并看到表/视图列表  
- **SC-002**: 95% 的合法只读查询在 5 秒内返回结果或空结果提示  
- **SC-003**: 90% 的首次使用者能在 10 分钟内完成至少一次查询  
- **SC-004**: 100% 的关键功能可在未登录状态下完成  
- **SC-005**: 至少 80% 的自然语言请求可生成可执行的查询（允许一次编辑）
