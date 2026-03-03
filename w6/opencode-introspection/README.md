# opencode-introspection

用于观测与分析 `opencode` 对话过程的仓库，包含两部分：

- 日志采集插件：按 turn 记录 LLM 输入/输出到 JSONL
- 前端可视化工具：打开 JSONL 并按 turn 展示结构化详情

## 1. 项目结构

```text
.
├─ plugins/
│  └─ log-conversation.ts      # 对话日志采集插件
├─ logs/                       # 采集后的 *.jsonl 日志文件（按 session 分文件）
├─ visualizer/                 # React + TypeScript + Vite 可视化应用
│  ├─ src/
│  │  ├─ App.tsx
│  │  ├─ parser.ts
│  │  ├─ types.ts
│  │  └─ components/
│  └─ styles/
│     ├─ design-token.css
│     ├─ design-tokens.css
│     └─ global.css
└─ specs/
   └─ visualizer-design-doc.md # 设计文档（目标态与实现说明）
```

## 2. 核心能力

### 2.1 日志采集（`plugins/log-conversation.ts`）

插件通过以下 hook/event 采集并关联 turn 级数据：

- hooks：
  - `experimental.chat.messages.transform`（捕获消息快照）
  - `experimental.chat.system.transform`（捕获 system 快照）
  - `chat.params`（创建 turn draft，记录输入参数）
  - `chat.headers`（补充 headers）
  - `event`（处理消息更新/增量）
- events：
  - `message.updated`
  - `message.part.updated`
  - `message.part.delta`

输出行为：

- 日志目录：`logs/`
- 日志文件：`logs/<session_id>.jsonl`
- 写入方式：逐行 JSON 追加（JSONL），并按文件串行写入避免并发写乱序

### 2.2 日志可视化（`visualizer/`）

当前实现（与设计文档目标态可能有差异）包含：

- 打开本地文件：支持 `.jsonl/.log/.txt`（含 `application/x-ndjson`）
- 逐行解析 JSON，坏行不会中断整体展示（会进入 Parse Errors）
- 左侧 Turn 列表：支持搜索、折叠、显示 finish reason / 时间 / output tokens
- 右侧详情区：
  - `System Prompts`
  - `Chat History`
  - `Tool Invocations`
- 底部状态栏展示 token 与时长统计
- Markdown 渲染：`react-markdown` + `remark-gfm`

## 3. 日志数据格式（摘要）

当前记录 schema：`opencode.llm.turn.v1`

常见顶层字段：

- `schema`
- `session_id`
- `turn_id`
- `turn_index`
- `user_message_id`
- `assistant_message_id`
- `started_at`
- `completed_at`
- `llm_input`
- `llm_output`

其中：

- `llm_input` 常见包含：`model/provider/agent/user_message/messages/system/params/headers/capture_meta`
- `llm_output` 当前写入：`assistant_message`（包含 `info` 与 `parts`）

更详细说明见：

- `specs/visualizer-design-doc.md`

## 4. 快速开始

### 4.1 启动可视化应用

```bash
cd visualizer
npm install
npm run dev
```

生产构建与预览：

```bash
cd visualizer
npm run build
npm run preview
```

> `visualizer/package.json` 当前脚本：`dev` / `build` / `preview`

### 4.2 采集与查看流程

1. 在你的 `opencode` 运行环境中启用 `plugins/log-conversation.ts`
2. 产生对话后，确认 `logs/` 目录下新增或追加 `*.jsonl`
3. 启动 `visualizer` 并在页面中打开目标 JSONL 文件
4. 在 Parse Errors 面板检查格式异常行（如有）

## 5. 开发说明

- 前端技术栈：React + TypeScript + Vite
- Markdown 渲染：`react-markdown` + `remark-gfm`
- 样式文件：
  - `visualizer/styles/design-token.css`（别名入口，内部 `@import ./design-tokens.css`）
  - `visualizer/styles/design-tokens.css`（token 实际定义）
  - `visualizer/styles/global.css`

## 6. 当前仓库状态

- 仓库当前已包含 `visualizer/node_modules` 与 `visualizer/dist`
- 已存在 `logs/` 目录，可用于直接演示可视化流程

如需减小仓库体积，建议将构建产物与依赖目录加入 `.gitignore` 并在后续提交中移除跟踪。
