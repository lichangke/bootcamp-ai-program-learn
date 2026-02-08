# Quickstart: 数据库查询工具

**Feature目录**: `D:/GithubCode/bootcamp-ai-program-learn/specs/001-db-query-tool`  
**目标**: 在本地启动后端与前端，完成连接数据库、SQL 查询、自然语言生成 SQL 的端到端验证。

## 1. 环境准备

- Python 3.12+
- `uv`（用于后端依赖与运行）
- Node.js 20+
- 可访问的 PostgreSQL 实例
- 环境变量：`OPENAI_API_KEY`

Windows PowerShell 示例：

```powershell
$env:OPENAI_API_KEY="<your-key>"
```

## 2. 后端启动（FastAPI）

```powershell
cd D:/GithubCode/bootcamp-ai-program-learn/backend
uv sync
uv run fastapi dev src/main.py --port 8000
```

### 后端关键约束

- CORS 允许所有 origin
- SQLite 持久化文件固定为：`~/.db_query/db_query.db`
- 仅允许 `SELECT` 查询；缺失 `LIMIT` 自动补 `LIMIT 1000`
- 所有 JSON 响应字段使用 camelCase

## 3. 前端启动（React + refine）

```powershell
cd D:/GithubCode/bootcamp-ai-program-learn/frontend
npm install
npm run dev
```

默认访问：`http://localhost:5173`

## 4. API 冒烟验证

### 4.1 添加数据库连接

```bash
curl -X PUT "http://localhost:8000/api/v1/dbs/local" \
  -H "Content-Type: application/json" \
  -d '{"url":"postgres://postgres:postgres@localhost:5432/postgres"}'
```

### 4.2 获取数据库列表

```bash
curl "http://localhost:8000/api/v1/dbs"
```

### 4.3 执行 SQL 查询

```bash
curl -X POST "http://localhost:8000/api/v1/dbs/local/query" \
  -H "Content-Type: application/json" \
  -d '{"sql":"SELECT * FROM users"}'
```

### 4.4 自然语言生成 SQL

```bash
curl -X POST "http://localhost:8000/api/v1/dbs/local/query/natural" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"查询用户表的所有信息"}'
```

## 5. 预期行为

- `PUT /dbs/{name}` 成功后可返回 metadata（tables/views/columns）
- 非法或非只读 SQL 会返回清晰错误信息
- 未登录即可访问所有接口（无认证/授权）
- 前端 SQL Editor 使用 Monaco，可预览并提交 SQL
