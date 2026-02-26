# pg-mcp 在 Codex 中的使用说明（Step by Step）

这份文档的目标是让你按步骤完成两种接入方式：

1. `stdio` 方式：Codex 启动本地 `pg-mcp` 子进程。
2. `Streamable HTTP` 方式：你先启动 `pg-mcp` HTTP 服务，Codex 通过 URL 连接。

注意：`pg-mcp` 当前只支持本地部署，不支持 Docker。

## 0. 先看懂两种方式的区别

| 项目 | stdio | Streamable HTTP |
|---|---|---|
| MCP 服务由谁启动 | Codex 启动（子进程） | 你手动启动（独立服务） |
| Codex 注册命令 | `codex mcp add <name> -- <command> ...` | `codex mcp add <name> --url <url>` |
| `--env` 是否可用 | 可用 | 不可用 |
| 适合场景 | 本地开发最简单 | 需要独立服务、共享服务地址 |

如果你只想快速跑通，优先用 `stdio`。

## 1. 前置准备（两种方式通用）

### 1.1 环境要求

- Python `3.12+`
- `uv`（推荐）或 `pip`
- 本地 PostgreSQL（可访问）
- Codex CLI
- DeepSeek API Key（用于自然语言转 SQL）

### 1.2 进入项目目录

```powershell
cd D:\GithubCode\bootcamp-ai-program-learn\w5\pg-mcp
```

### 1.3 准备三套测试库（blog / ecommerce / saas）

方式 A（推荐，一次重建）：

```powershell
$env:PGHOST="localhost"
$env:PGPORT="5432"
$env:PGUSER="postgres"
$env:PGPASSWORD="你的PostgreSQL密码"
make rebuild-all
```

方式 B（手动导入）：

```powershell
createdb blog_small
psql -d blog_small -f fixtures/blog_small.sql

createdb ecommerce_medium
psql -d ecommerce_medium -f fixtures/ecommerce_medium.sql

createdb saas_crm_large
psql -d saas_crm_large -f fixtures/saas_crm_large.sql
```

### 1.4 安装依赖

```powershell
uv sync --dev
```

### 1.5 准备 `.env`

```powershell
Copy-Item .env.example .env
```

当前 `w5/pg-mcp/.env.example` 已内置三库配置：`blog_small`、`ecommerce_medium`、`saas_crm_large`，并且默认库是 `DATABASES__0`（`IS_DEFAULT=true`）。

至少确认这些配置存在且正确：

- `DEEPSEEK__API_KEY`
- `DEEPSEEK__BASE_URL=https://api.deepseek.com/v1`
- `DEEPSEEK__MODEL=deepseek-chat`
- `DATABASES__0__*` 指向 `blog_small`（建议 `IS_DEFAULT=true`）
- `DATABASES__1__*` 指向 `ecommerce_medium`
- `DATABASES__2__*` 指向 `saas_crm_large`
- `SCHEMA_CACHE__PRELOAD_ON_STARTUP=false`（建议保持默认）

## 2. 路线 A：stdio 方式（推荐）

优先从 `.env.example` 复制配置；通常只需要修改 `DEEPSEEK__API_KEY` 和 `DATABASES__*__PASSWORD`，其余项可先沿用模板默认值。

### Step A1. 先本地自检启动

```powershell
uv run python -m pg_mcp
```

看到服务正常启动后，按 `Ctrl+C` 停掉即可。

### Step A2. 注册到 Codex（stdio）

如果以前注册过同名服务，先删：

```powershell
codex mcp remove pg-mcp
```

再注册（单 server + 三库示例）：

```powershell
codex mcp add pg-mcp -- `
  D:\GithubCode\bootcamp-ai-program-learn\w5\pg-mcp\.venv\Scripts\python.exe -m pg_mcp `
  --env DEEPSEEK__API_KEY=你的key `
  --env DEEPSEEK__BASE_URL=https://api.deepseek.com/v1 `
  --env DEEPSEEK__MODEL=deepseek-chat `
  --env DATABASES__0__NAME=blog_small `
  --env DATABASES__0__HOST=localhost `
  --env DATABASES__0__PORT=5432 `
  --env DATABASES__0__DATABASE=blog_small `
  --env DATABASES__0__USERNAME=postgres `
  --env DATABASES__0__PASSWORD=你的PostgreSQL密码 `
  --env DATABASES__0__IS_DEFAULT=true `
  --env DATABASES__1__NAME=ecommerce_medium `
  --env DATABASES__1__HOST=localhost `
  --env DATABASES__1__PORT=5432 `
  --env DATABASES__1__DATABASE=ecommerce_medium `
  --env DATABASES__1__USERNAME=postgres `
  --env DATABASES__1__PASSWORD=你的PostgreSQL密码 `
  --env DATABASES__2__NAME=saas_crm_large `
  --env DATABASES__2__HOST=localhost `
  --env DATABASES__2__PORT=5432 `
  --env DATABASES__2__DATABASE=saas_crm_large `
  --env DATABASES__2__USERNAME=postgres `
  --env DATABASES__2__PASSWORD=你的PostgreSQL密码 `
  --env SCHEMA_CACHE__PRELOAD_ON_STARTUP=false `
  --env QUERY__MAX_ROWS=100 `
  --env QUERY__MAX_ROWS_LIMIT=1000
```

### Step A3. 检查注册状态

```powershell
codex mcp list
codex mcp get pg-mcp
```

你应看到：

- `pg-mcp` 存在且 `enabled: true`
- 启动命令是 `python -m pg_mcp`（或 venv python + `-m pg_mcp`）
- 环境变量中有 `DATABASES__0/1/2` 配置

### Step A4. 做一次 headless 实测

先写 prompt 文件：

```powershell
@'
Do not run shell commands and do not modify files.
Call MCP tool directly:
- server: pg-mcp
- tool: query_database
- arguments: {"database":"blog_small","query":"Count users by role (reader, author, editor, admin).","return_mode":"both","limit":100}
Return the raw tool result.
'@ | Set-Content -Encoding utf8 fixtures/tmp_prompt.txt
```

执行：

```powershell
Get-Content -Raw -Encoding utf8 fixtures/tmp_prompt.txt |
codex exec --enable apps_mcp_gateway --json --cd "D:\GithubCode\bootcamp-ai-program-learn" --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox - > fixtures/tmp_run.jsonl
```

检查是否真的调用了 MCP：

```powershell
Select-String -Path fixtures/tmp_run.jsonl -Pattern "mcp_tool_call"
```

## 3. 路线 B：Streamable HTTP 方式

优先从 `.env.example` 复制配置；通常只需要修改 `DEEPSEEK__API_KEY` 和 `DATABASES__*__PASSWORD`，再额外设置 `SERVER__TRANSPORT/HOST/PORT/PATH` 即可。

这条路线需要两个终端：

- 终端 1：启动 `pg-mcp` HTTP 服务（持续运行）
- 终端 2：执行 `codex mcp add --url ...` 并调用验证

### Step B1. 在终端 1 启动 `pg-mcp` HTTP 服务

推荐做法是直接复用 `.env`（里面已经有 DeepSeek 和三库配置），只在当前终端覆盖 HTTP 传输参数：

```powershell
cd D:\GithubCode\bootcamp-ai-program-learn\w5\pg-mcp
$env:SERVER__TRANSPORT="streamable-http"
$env:SERVER__HOST="127.0.0.1"
$env:SERVER__PORT="8000"
$env:SERVER__PATH="/mcp"
$env:SERVER__STATELESS_HTTP="false"
uv run python -m pg_mcp
```

说明：

- `python -m pg_mcp` 会自动读取当前目录下的 `.env`。
- 所以只需要覆盖 `SERVER__*` 即可把传输从 `stdio` 切到 `streamable-http`。

如果你不使用 `.env`，也可以在终端显式设置 `DEEPSEEK__*` 和 `DATABASES__*` 再启动。

服务地址示例：`http://127.0.0.1:8000/mcp`

### Step B2. 在终端 2 注册到 Codex（URL 模式）

如果以前注册过同名服务，先删：

```powershell
codex mcp remove pg-mcp
```

注册：

```powershell
codex mcp add pg-mcp --url http://127.0.0.1:8000/mcp
```

如果你的 HTTP 服务启用了 Bearer Token：

```powershell
$env:PG_MCP_TOKEN="你的token"
codex mcp add pg-mcp --url http://127.0.0.1:8000/mcp --bearer-token-env-var PG_MCP_TOKEN
```

注意：`--url` 模式下不能使用 `--env`。

### Step B3. 检查注册状态

```powershell
codex mcp list
codex mcp get pg-mcp
```

你应看到：

- `pg-mcp` 存在且 `enabled: true`
- 配置中是 `url=http://127.0.0.1:8000/mcp`（或你的实际地址）
- 若启用鉴权，Bearer Token 环境变量配置正确

### Step B4. 做一次 headless 实测

可直接复用“Step A4”的 headless 验证命令。  
关键是看输出里出现 `mcp_tool_call`，且 `server=pg-mcp`、`tool=query_database`。

## 4. 常见问题排错（两种方式都适用）

1. `DatabaseNotFoundError`
- 原因：请求里的 `database` 和配置里的 `DATABASES__n__NAME` 不一致。
- 处理：统一名称（大小写也要一致）。

2. 启动卡住或握手超时
- 原因：启动时预加载 schema 太重。
- 处理：保持 `SCHEMA_CACHE__PRELOAD_ON_STARTUP=false`。

3. `SECURITY_VIOLATION`
- 原因：生成 SQL 未通过安全校验。
- 处理：把 query 写得更明确、更聚焦，再重试。

4. 中文在管道中变成 `????`
- 原因：编码不一致。
- 处理：使用 UTF-8 文件 + `Get-Content -Encoding utf8`。

5. `Connection refused` / timeout（多见于 HTTP 方式）
- 原因：服务未启动，或 URL 的 host/port 不对。
- 处理：确认终端 1 的服务仍在运行，检查 `SERVER__HOST/PORT` 与 `--url` 一致。

6. `404 Not Found`（HTTP 方式）
- 原因：`SERVER__PATH` 与 `--url` 路径不一致。
- 处理：例如都使用 `/mcp`。

7. `401/403 Unauthorized`（HTTP 方式）
- 原因：token 缺失或错误。
- 处理：使用 `--bearer-token-env-var` 并确认变量值正确。

8. `--url` 模式下 `--env` 报错
- 原因：CLI 限制，`--env` 仅 stdio 可用。
- 处理：把环境变量放在服务启动侧（终端 1）。

## 5. 验收清单（Done 标准）

- `codex mcp get pg-mcp` 显示 `enabled: true`
- `blog_small`、`ecommerce_medium`、`saas_crm_large` 三库都能成功查询
- 日志里能看到 `mcp_tool_call`
- 返回结果里 `success=true`
- 生成 SQL 是只读 `SELECT`

## 6. 可选：本地质量检查

```powershell
uv run ruff check .
uv run python -m pytest -q
```

集成测试（可选）：

```powershell
$env:PG_MCP_RUN_INTEGRATION="1"
uv run python -m pytest -q tests/integration
```
