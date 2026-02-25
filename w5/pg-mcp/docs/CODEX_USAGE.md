# pg-mcp 在 Codex 中的使用说明（中文实操版）

这份文档的目标很直接：你照着做，就能把 `pg-mcp` 跑起来，并在 Codex 里稳定使用。

你将完成这几件事：

1. 启动 `pg-mcp` 成功。
2. 把它注册到 Codex。
3. 用一个 server 同时连三套库。
4. 跑一次 headless 调用，确认确实走了 MCP 工具，结果也正确。

注意：`pg-mcp` 当前只支持本地部署，不支持 Docker。

## 1. 先准备好这些环境

- 系统：Windows / macOS / Linux 都可以
- Python：`3.12+`
- `uv`（推荐）或 `pip`
- 本地可访问的 PostgreSQL
- Codex CLI
- DeepSeek API Key（用于自然语言转 SQL）

## 2. 准备三套数据库（blog/ecommerce/saas）

先进入目录：

```powershell
cd w5/pg-mcp
```

### 方式 A（推荐）：直接用 Makefile 一次重建三库

```powershell
$env:PGHOST="localhost"
$env:PGPORT="5432"
$env:PGUSER="postgres"
$env:PGPASSWORD="你的PostgreSQL密码"
make rebuild-all
```

### 方式 B：手动用 psql 导入

```powershell
createdb blog_small
psql -d blog_small -f fixtures/blog_small.sql

createdb ecommerce_medium
psql -d ecommerce_medium -f fixtures/ecommerce_medium.sql

createdb saas_crm_large
psql -d saas_crm_large -f fixtures/saas_crm_large.sql
```

最后你应该有这三个库：

- `blog_small`
- `ecommerce_medium`
- `saas_crm_large`

## 3. 安装 pg-mcp 依赖

在 `w5/pg-mcp` 目录执行：

```powershell
uv sync --dev
```

如果你不用 `uv`，也可以自己建 venv 再按 `pyproject.toml` 安装依赖。

## 4. 配置环境变量（很关键）

先复制模板：

```powershell
Copy-Item .env.example .env
```

然后把 `.env` 至少改好这些项：

- `DEEPSEEK__API_KEY`
- `DEEPSEEK__BASE_URL`（默认可用：`https://api.deepseek.com/v1`）
- `DEEPSEEK__MODEL`（默认可用：`deepseek-chat`）
- `DATABASES__0__*`（指向 `blog_small`）
- `DATABASES__1__*`（指向 `ecommerce_medium`）
- `DATABASES__2__*`（指向 `saas_crm_large`）

实战建议：

- 只设置一个默认库：例如 `DATABASES__0__IS_DEFAULT=true`
- `SCHEMA_CACHE__PRELOAD_ON_STARTUP=false` 建议保持默认（可避免 MCP 客户端启动握手超时）
- `QUERY__MAX_ROWS=100`、`QUERY__MAX_ROWS_LIMIT=1000` 这类限制建议保留

## 5. 先本地试启动一次（可选但强烈推荐）

```powershell
uv run python -m pg_mcp
```

能正常启动就说明核心配置没问题，然后 `Ctrl+C` 停掉即可。

## 6. 把 pg-mcp 注册到 Codex

你有两种方式，选一种就行。

### 方式 6.1：用 `codex mcp add`（推荐）

下面是单 server + 三库配置示例（把密码和 key 替换掉）：

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

### 方式 6.2：手动改 `.codex/config.toml`

把下面这段加进去（或按这个结构更新已有配置）：

```toml
[mcp_servers.pg-mcp]
command = "D:\\GithubCode\\bootcamp-ai-program-learn\\w5\\pg-mcp\\.venv\\Scripts\\python.exe"
args = ["-m", "pg_mcp"]
cwd = "D:\\GithubCode\\bootcamp-ai-program-learn\\w5\\pg-mcp"

[mcp_servers.pg-mcp.env]
DEEPSEEK__API_KEY = "你的key"
DEEPSEEK__BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK__MODEL = "deepseek-chat"

DATABASES__0__NAME = "blog_small"
DATABASES__0__HOST = "localhost"
DATABASES__0__PORT = "5432"
DATABASES__0__DATABASE = "blog_small"
DATABASES__0__USERNAME = "postgres"
DATABASES__0__PASSWORD = "你的PostgreSQL密码"
DATABASES__0__IS_DEFAULT = "true"

DATABASES__1__NAME = "ecommerce_medium"
DATABASES__1__HOST = "localhost"
DATABASES__1__PORT = "5432"
DATABASES__1__DATABASE = "ecommerce_medium"
DATABASES__1__USERNAME = "postgres"
DATABASES__1__PASSWORD = "你的PostgreSQL密码"

DATABASES__2__NAME = "saas_crm_large"
DATABASES__2__HOST = "localhost"
DATABASES__2__PORT = "5432"
DATABASES__2__DATABASE = "saas_crm_large"
DATABASES__2__USERNAME = "postgres"
DATABASES__2__PASSWORD = "你的PostgreSQL密码"

SCHEMA_CACHE__PRELOAD_ON_STARTUP = "false"
QUERY__MAX_ROWS = "100"
QUERY__MAX_ROWS_LIMIT = "1000"
```

## 7. 检查 Codex 里是否注册成功

```powershell
codex mcp list
codex mcp get pg-mcp
```

你要看到这些关键信息：

- `pg-mcp` 存在并且 `enabled: true`
- 启动命令是 `python -m pg_mcp`（或你的 venv python + `-m pg_mcp`）
- 环境变量里有 `DATABASES__0/1/2` 三套配置

## 8. 跑一次 Headless 验证（并检查是否真的调用 MCP）

强烈建议用 UTF-8 文件传 prompt，避免中文在管道里变成 `????`。

### 第一步：写 prompt 文件

```powershell
@'
Do not run shell commands and do not modify files.
Call MCP tool directly:
- server: pg-mcp
- tool: query_database
- arguments: {"database":"blog_small","query":"Count users by role (reader, author, editor, admin).","return_mode":"both","limit":100}
Return the raw tool result.
'@ | Set-Content -Encoding utf8 w5/pg-mcp/fixtures/tmp_prompt.txt
```

### 第二步：执行 headless

```powershell
Get-Content -Raw -Encoding utf8 w5/pg-mcp/fixtures/tmp_prompt.txt |
codex exec --enable apps_mcp_gateway --json --cd "D:\GithubCode\bootcamp-ai-program-learn" --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox - > w5/pg-mcp/fixtures/tmp_run.jsonl
```

### 第三步：确认日志里有 MCP 调用

```powershell
Select-String -Path w5/pg-mcp/fixtures/tmp_run.jsonl -Pattern "mcp_tool_call"
```

你需要确认：

- `server` 是 `pg-mcp`
- `tool` 是 `query_database`

然后看 JSON 里的 `structured_content`：

- `success=true`
- `data.sql`（生成的 SQL）
- `data.result.rows`（查询结果）

## 9. 最小成功标准（照这个验收）

- `codex mcp get pg-mcp` 显示 `enabled: true`
- 下面三个库都能成功查询：
  - `database="blog_small"`
  - `database="ecommerce_medium"`
  - `database="saas_crm_large"`
- 输出日志里能看到 `mcp_tool_call` 且 `success=true`
- 生成 SQL 都是只读 `SELECT`

## 10. 常见问题与处理

1. `DatabaseNotFoundError`
- 原因：你请求里的 `database` 名字和配置里的 `DATABASES__n__NAME` 对不上
- 处理：两边名字改成完全一致

2. 启动卡住或握手超时
- 原因：启动时预加载 schema 太重
- 处理：确保 `SCHEMA_CACHE__PRELOAD_ON_STARTUP=false`

3. `SECURITY_VIOLATION`
- 原因：自然语言生成的 SQL 被安全校验拦截
- 处理：把 query 说得更清楚、更简单，再试一次

4. 中文 query 变成 `????`
- 原因：shell 编码不一致
- 处理：按第 8 节，用 UTF-8 文件 + `Get-Content -Encoding utf8`

5. LLM/HTTP 报错
- 检查：`DEEPSEEK__API_KEY`、`DEEPSEEK__BASE_URL`、网络连通性、模型名

## 11. 可选：本地质量检查

在 `w5/pg-mcp` 目录执行：

```powershell
uv run ruff check .
uv run python -m pytest -q
```

如果要跑集成测试：

```powershell
$env:PG_MCP_RUN_INTEGRATION="1"
uv run python -m pytest -q tests/integration
```

