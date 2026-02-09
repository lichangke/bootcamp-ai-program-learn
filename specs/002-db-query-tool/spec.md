# Feature Specification: 数据库查询工具

**Feature Branch**: `002-db-query-tool`
**Created**: 2026-02-08
**Status**: Draft
**Input**: User description: "这是一个数据库查询工具，用户可以添加一个 db url, 系统会连接到数据库，获取数据库的 metadata，然后将数据库中的 table 和 view 的 信息展示出来，然后用户可以自己输入 sql 查询，也可以通过自然语言来生成 sql 查询。数据库连接字符串和 metadata 会持久化存储以便复用。所有 SQL 语句需要经过解析验证，确保语法正确且仅包含 SELECT 语句。查询结果以 JSON 格式返回，前端组织成表格展示。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 连接数据库并浏览结构信息 (Priority: P1)

用户可以添加一个数据库连接，系统验证连接后获取表和视图的结构信息，并清晰展示出来，便于后续查询。

**Why this priority**: 不完成连接和结构展示，后续查询与自然语言功能都无法使用。

**Independent Test**: 仅实现连接与结构展示即可验证：添加连接后能看到表/视图/字段列表。

**Acceptance Scenarios**:

1. **Given** 用户提供有效的数据库连接 URL，**When** 保存连接，**Then** 系统成功连接、获取 metadata 并显示数据库的表/视图及字段信息。
2. **Given** 用户提供无效连接 URL 或数据库不可达，**When** 保存连接，**Then** 系统显示明确错误信息并不保存该连接。
3. **Given** 数据库连接成功但无表或视图，**When** 获取 metadata，**Then** 系统显示空状态提示。

---

### User Story 2 - 执行只读 SQL 查询并查看结果 (Priority: P2)

用户在已连接的数据库上输入 SQL 查询，系统校验为只读查询后执行，并以表格展示结果。

**Why this priority**: 这是工具的核心价值：让用户直接查询数据并获得可视化结果。

**Independent Test**: 选择一个已保存连接，执行只读查询并看到结果表。

**Acceptance Scenarios**:

1. **Given** 用户输入合法只读查询且未包含 `LIMIT`，**When** 执行查询，**Then** 系统自动添加 `LIMIT 1000` 并返回结果。
2. **Given** 用户输入非只读语句（如 INSERT/UPDATE/DELETE），**When** 执行查询，**Then** 系统通过 SQL 解析器检测并拒绝执行，提示只允许 SELECT 语句。
3. **Given** 用户输入包含多条语句的 SQL，**When** 执行查询，**Then** 系统检测并拒绝执行，提示不允许多语句输入。
4. **Given** 用户输入语法错误的 SQL，**When** 执行查询，**Then** 系统通过解析器检测并返回具体的语法错误信息。

---

### User Story 3 - 自然语言生成查询 (Priority: P3)

用户用自然语言描述想要的数据，系统基于已知表/视图结构生成 SQL，用户确认后执行并查看结果。

**Why this priority**: 降低 SQL 使用门槛，提升非技术用户的可用性。

**Independent Test**: 在有结构信息的前提下，输入自然语言需求并得到可执行的只读查询。

**Acceptance Scenarios**:

1. **Given** 用户输入自然语言问题且数据库 metadata 已加载，**When** 生成查询，**Then** 系统将 metadata 作为上下文传递给 LLM，生成 SQL 并展示给用户。
2. **Given** 生成的 SQL 不满足只读限制或包含语法错误，**When** 用户尝试执行，**Then** 系统通过解析器检测并阻止执行，提示具体原因。
3. **Given** 用户的自然语言描述涉及不存在的表或字段，**When** 生成查询，**Then** LLM 基于可用 metadata 生成最接近的查询或提示无法生成。

---

### Edge Cases

- 连接超时或数据库不可达时如何提示用户？
- 目标数据库没有表或视图时如何展示空状态？
- 查询返回空结果集时如何展示？
- 用户输入包含多条语句的 SQL 时如何处理？
- 自然语言描述涉及不存在的表/字段时如何处理？
- SQL 语法错误时如何提供有用的错误信息？
- 数据库 metadata 发生变化（表被删除/添加）时如何处理？
- 查询执行时间过长时如何处理？
- 数据库返回的数据类型无法序列化为 JSON 时如何处理？

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 允许用户创建并保存数据库连接（名称 + 连接 URL）。
- **FR-002**: 系统 MUST 在保存连接时验证连接可用性，并获取表/视图/字段结构信息（metadata）。
- **FR-003**: 系统 MUST 持久化连接信息与 metadata 以便复用，无需每次重新获取。
- **FR-004**: 系统 MUST 展示所选数据库的表与视图列表及字段信息（名称、类型）。
- **FR-005**: 系统 MUST 允许用户提交 SQL 查询并返回 JSON 格式结果。
- **FR-006**: 系统 MUST 使用 SQL 解析器验证所有输入的 SQL 语句，确保语法正确。
- **FR-007**: 系统 MUST 仅允许只读查询（仅 `SELECT`），并拒绝其他语句类型（INSERT、UPDATE、DELETE 等）。
- **FR-008**: 系统 MUST 拒绝包含多条语句的输入（防止 SQL 注入和意外操作）。
- **FR-009**: 当查询未包含 `LIMIT` 子句时，系统 MUST 自动添加 `LIMIT 1000` 以防止返回过多数据。
- **FR-010**: 系统 MUST 允许用户通过自然语言生成 SQL，并在执行前展示生成的 SQL 语句供用户确认。
- **FR-011**: 系统 MUST 在生成自然语言查询时，将数据库 metadata（表/视图/字段信息）作为上下文提供给 LLM。
- **FR-012**: 系统 MUST 提供清晰、可理解的错误提示（连接失败、语法错误、只读限制违规、解析失败）。
- **FR-013**: 系统 MUST 在无登录/无权限配置的前提下可用（符合项目 constitution）。
- **FR-014**: 系统 MUST 以 JSON 格式返回查询结果，包含列信息和行数据。
- **FR-015**: 系统 MUST 支持刷新已保存连接的 metadata（当数据库结构发生变化时）。

### Key Entities *(include if feature involves data)*

- **DatabaseConnection**: 用户保存的数据库连接信息（名称、连接 URL、状态、创建时间、最后更新时间）。
- **SchemaMetadata**: 数据库结构元数据的完整快照（数据库名称、获取时间、表和视图列表）。
- **TableMetadata**: 表或视图的结构信息（名称、类型[表/视图]、字段列表、主键信息）。
- **ColumnMetadata**: 字段信息（名称、数据类型、是否可空、默认值）。
- **QueryRequest**: 用户提交的查询请求（查询类型[SQL/自然语言]、查询内容、目标连接）。
- **QueryResult**: 查询执行结果（列定义、行数据、总行数、执行时间）。
- **QueryError**: 查询或连接错误（错误类型、错误代码、用户可读提示、技术详情）。
- **NaturalLanguageContext**: 自然语言查询的上下文信息（相关表/视图 metadata、用户问题、生成的 SQL）。

## Assumptions

- 该工具为单用户或受信环境使用，不需要登录或权限控制（符合项目 constitution）。
- 初始版本支持 PostgreSQL 数据库连接（可扩展到其他数据库类型）。
- 数据库 metadata 在保存连接时获取并持久化，后续可按需刷新。
- 用户有权限访问目标数据库的系统表/视图以获取 metadata。
- 查询结果的数据量在合理范围内（通过 LIMIT 1000 限制）。
- 自然语言查询使用 LLM（如 OpenAI）生成 SQL，需要 API 密钥。
- SQL 解析器能够准确识别 SELECT 语句和多语句输入。
- 前端能够处理 JSON 格式的查询结果并渲染为表格。
- 数据库连接信息和 metadata 存储在本地持久化存储中（符合 constitution 的 `~/.db_query/db_query.db` 要求）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 新用户在 2 分钟内完成连接并看到结构信息的成功率 ≥ 90%。
- **SC-002**: 95% 的合法只读查询在 5 秒内返回结果（在典型规模数据集上）。
- **SC-003**: 当用户未提供 `LIMIT` 时，100% 的查询结果行数被限制在 1000 行以内。
- **SC-004**: 至少 80% 的自然语言查询在首次生成时可得到可执行的只读 SQL。
