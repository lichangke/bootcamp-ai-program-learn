# Project Alpha 需求与设计文档

**文档版本**: v1.1  
**创建日期**: 2026-02-14  
**状态**: Draft

## 1. 项目背景与目标

Project Alpha 是一个轻量级 ticket 管理工具，核心目标是让用户通过“标签”快速分类、检索和管理任务。系统不引入用户登录与权限体系，默认单用户或受信任内网场景。

### 1.1 业务目标

1. 降低任务管理复杂度，支持快速记录和更新 ticket。
2. 通过标签实现多维分类和聚合查看。
3. 提供基于标题的快速搜索，提高定位效率。

### 1.2 技术约束

1. 数据库: PostgreSQL
2. 后端: Python + FastAPI
3. 前端: TypeScript + Vite + Tailwind CSS + shadcn/ui

### 1.3 代码目录约束

1. 项目代码根目录固定为 `./w1/project-alpha`。
2. 本文档中所有实现路径均相对此目录展开。
3. 规范建议目录如下：

```text
./w1/project-alpha/
  backend/
  frontend/
  tests/
```

## 2. 范围定义

### 2.1 In Scope（本期范围）

1. Ticket 的创建、编辑、删除、完成、取消完成。
2. 标签的编辑、删除，以及与 ticket 的关联管理。
3. 按标签筛选 ticket 列表。
4. 按标题关键词搜索 ticket。
5. 提供基础的 API 与前端页面实现以上功能。

### 2.2 Out of Scope（本期不做）

1. 用户注册、登录、权限控制、多租户。
2. 附件上传、评论、提醒通知、审计日志。
3. 高级搜索（例如全文检索、布尔表达式）。
4. 复杂报表与数据分析看板。

## 3. 用户故事与验收场景

### 3.1 用户故事 1：管理 Ticket（P1）

作为用户，我希望能创建、编辑、删除、完成或取消完成 ticket，以管理日常任务。

**验收场景**:

1. 给定用户填写了合法标题，提交创建后系统返回 ticket 并显示在列表。
2. 给定 ticket 已存在，用户修改标题/描述后可立即在列表中看到更新结果。
3. 给定 ticket 状态为未完成，点击“完成”后状态更新为已完成。
4. 给定 ticket 状态为已完成，点击“取消完成”后状态更新为未完成。
5. 给定 ticket 已存在，用户执行删除后该 ticket 不再出现在列表中。

### 3.2 用户故事 2：管理标签（P1）

作为用户，我希望能给 ticket 打标签，并能编辑或删除标签，以便更好地分类任务。

**验收场景**:

1. 用户可为 ticket 选择一个或多个标签并保存。
2. 编辑标签名称后，关联 ticket 的显示同步更新。
3. 删除标签后，该标签从系统中移除，ticket 与该标签的关联自动清理。

### 3.3 用户故事 3：按标签查看（P2）

作为用户，我希望按标签筛选 ticket 列表，快速聚焦某类任务。

**验收场景**:

1. 选择单个标签时，列表仅显示包含该标签的 ticket。
2. 清除筛选条件后，恢复展示全部 ticket。

### 3.4 用户故事 4：按标题搜索（P2）

作为用户，我希望输入标题关键词搜索 ticket，快速定位目标任务。

**验收场景**:

1. 输入关键词后，列表实时或提交后返回匹配标题的 ticket。
2. 关键词为空时，展示当前筛选条件下的完整列表。

## 4. 功能需求（Functional Requirements）

1. **FR-001**: 系统必须支持创建 ticket，至少包含 `title`、可选 `description`、可选标签集合。
2. **FR-002**: 系统必须支持编辑 ticket 的 `title`、`description`、标签集合。
3. **FR-003**: 系统必须支持删除 ticket。
4. **FR-004**: 系统必须支持 ticket 状态在“未完成/已完成”之间切换。
5. **FR-005**: 系统必须支持创建标签并去重（标签名全局唯一，大小写不敏感比较）。
6. **FR-006**: 系统必须支持编辑标签名称，并保证重名校验。
7. **FR-007**: 系统必须支持删除标签，并清理关联关系。
8. **FR-008**: 系统必须支持按单个标签筛选 ticket 列表。
9. **FR-009**: 系统必须支持按 `title` 关键词搜索 ticket，采用模糊匹配。
10. **FR-010**: 系统必须支持分页查询 ticket 列表（默认 20 条/页）。
11. **FR-011**: 系统必须返回标准化错误结构，便于前端展示。
12. **FR-012**: 系统必须提供健康检查接口用于运行监控。

## 5. 非功能需求（Non-Functional Requirements）

1. **NFR-001 性能**: 在 1 万条 ticket 数据规模下，列表查询（含标签筛选或标题搜索）P95 响应时间小于 500ms。
2. **NFR-002 可维护性**: 后端采用分层结构（Router/Service/Repository），便于单元测试与扩展。
3. **NFR-003 可用性**: 前端关键操作（创建、编辑、删除、状态切换）均有成功/失败反馈。
4. **NFR-004 一致性**: 标签删除与关联清理在同一事务中完成。
5. **NFR-005 兼容性**: API 返回 JSON，遵循 REST 风格，便于多前端接入。

## 6. 领域模型与数据设计

## 6.1 实体定义

1. **Ticket**
2. **Tag**
3. **TicketTag**（多对多关联表）

### 6.2 PostgreSQL 表结构（建议）

```sql
CREATE TABLE tickets (
  id BIGSERIAL PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  description TEXT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'open', -- open | done
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ NULL
);

CREATE TABLE tags (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(50) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uk_tags_name_ci ON tags (LOWER(name));

CREATE TABLE ticket_tags (
  ticket_id BIGINT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  tag_id BIGINT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY (ticket_id, tag_id)
);

CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_title_trgm ON tickets USING gin (title gin_trgm_ops);
CREATE INDEX idx_ticket_tags_tag_id ON ticket_tags(tag_id);
```

### 6.3 状态模型

1. `open`: 未完成
2. `done`: 已完成

状态流转:

1. `open -> done`（完成）
2. `done -> open`（取消完成）

## 7. 后端设计（FastAPI）

### 7.1 分层架构

1. `api/routers`: HTTP 路由与参数校验
2. `services`: 业务规则（状态流转、标签去重、事务边界）
3. `repositories`: SQL 访问层
4. `models/schemas`: Pydantic 请求响应模型
5. `core`: 配置、数据库连接、异常处理

### 7.2 关键接口设计

```text
GET    /api/health
GET    /api/tickets
POST   /api/tickets
GET    /api/tickets/{ticket_id}
PUT    /api/tickets/{ticket_id}
DELETE /api/tickets/{ticket_id}
PATCH  /api/tickets/{ticket_id}/complete
PATCH  /api/tickets/{ticket_id}/reopen

GET    /api/tags
POST   /api/tags
PUT    /api/tags/{tag_id}
DELETE /api/tags/{tag_id}
```

### 7.3 典型查询参数

`GET /api/tickets?tag_id=3&q=deploy&page=1&page_size=20&status=open`

参数说明:

1. `tag_id`: 可选，按标签筛选
2. `q`: 可选，按标题模糊搜索
3. `status`: 可选，`open|done`
4. `page/page_size`: 分页参数

### 7.4 响应结构约定

成功响应:

```json
{
  "data": {},
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 124
  }
}
```

错误响应:

```json
{
  "error": {
    "code": "TAG_NAME_CONFLICT",
    "message": "标签名称已存在",
    "details": {}
  }
}
```

### 7.5 关键业务规则

1. `title` 必填，长度 1-200。
2. 标签名称长度建议 1-50，去除首尾空格后判重。
3. 删除标签前不禁止操作，直接通过 `ON DELETE CASCADE` 清理关联。
4. 编辑 ticket 标签时，采用“全量覆盖”策略，便于前端同步状态。
5. 完成 ticket 时写入 `completed_at`；取消完成时清空该字段。

## 8. 前端设计（TypeScript + Vite + Tailwind + shadcn）

### 8.1 页面结构

1. `TicketListPage`:
   - 搜索框（按标题）
   - 标签筛选器
   - ticket 列表（标题、状态、标签、更新时间）
   - 分页器
2. `TicketEditorDialog`:
   - 创建/编辑 ticket 表单
   - 标签多选
3. `TagManagerDialog`:
   - 标签列表
   - 新增/编辑/删除标签

### 8.2 状态管理建议

1. 使用 TanStack Query 管理服务端状态（列表、详情、标签）。
2. 本地 UI 状态（弹窗开关、输入框）使用 React state。
3. 关键 mutation 成功后，通过 query invalidation 自动刷新列表。

### 8.3 交互细节

1. 搜索输入 300ms 防抖，减少请求频率。
2. 删除操作需二次确认。
3. 所有异步操作显示 loading 状态和 toast 提示。
4. 空状态文案明确区分“暂无数据”和“无匹配结果”。

## 9. 安全与稳定性

1. 后端必须使用参数化查询，防止 SQL 注入。
2. 所有写操作接口校验请求体，返回统一错误码。
3. 限制分页大小上限（例如 `page_size <= 100`），避免滥用。
4. 关键写操作使用数据库事务，避免部分成功。

## 10. 测试策略

### 10.1 后端测试

1. 单元测试:
   - ticket 状态切换规则
   - 标签重名校验规则
   - 标签关联覆盖逻辑
2. 集成测试:
   - ticket CRUD 全链路
   - 标签 CRUD + 关联清理
   - 列表查询（标签筛选 + 标题搜索 + 分页）

### 10.2 前端测试

1. 组件测试:
   - 列表渲染与空状态
   - 表单校验与提交行为
2. E2E 冒烟:
   - 创建 ticket -> 打标签 -> 按标签筛选 -> 搜索 -> 完成 -> 取消完成 -> 删除

## 11. 交付里程碑（建议）

1. **M1 数据层与 API（2-3 天）**
   - 完成表结构、迁移、后端基础接口与单元测试
2. **M2 前端核心流程（2-3 天）**
   - 完成列表、编辑弹窗、标签管理、筛选搜索
3. **M3 联调与验收（1-2 天）**
   - 修复边界问题，补齐测试，整理部署说明

## 12. 验收标准（Definition of Done）

1. 用户可在 UI 中完成 ticket 的创建、编辑、删除、完成、取消完成。
2. 用户可管理标签并在 ticket 上正确生效。
3. 列表支持按标签筛选与按标题搜索，并可分页。
4. 后端接口通过核心测试用例，前端冒烟流程通过。
5. 文档与代码一致，关键错误场景有明确提示。
