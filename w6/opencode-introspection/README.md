# opencode-introspection

用于本地查看 OpenCode 会话日志（JSONL）的可视化工具仓库。  
当前可用前端位于 `./visualizer`，技术栈为 React + TypeScript + Vite。

## 核心能力（基于 `./visualizer` 实现）

- 导入本地日志文件：支持 `.jsonl`、`.log`、`.txt`、`application/x-ndjson`
- 逐行解析 JSONL：忽略空行，记录解析失败行号、错误信息和原始文本
- Turn 自动排序：
  - 优先按 `turn_index`（支持 number / 可转 number 的 string）排序
  - 其次按日志行号排序
- 左侧 Turn 列表：
  - 展示 `turn_index`（或行号）、`finish reason`、开始时间、输出 token
  - 支持关键字搜索（`turn_index` / `turn_id` / `user_message_id` / `assistant_message_id` / `finish`）
  - 侧栏可折叠
- 右侧 Turn 详情：
  - `System Prompts`
  - `Chat History`
  - `Tool Invocations`
  - 三个分区和每条记录都可单独折叠
  - 支持上一条/下一条切换
- Markdown 渲染：
  - 使用 `react-markdown` + `remark-gfm`
  - 链接新窗口打开
  - 图片不直接渲染（显示占位文本）
- Tool 关联分析：
  - 基于启发式规则做聊天-工具关联：在同一 `role + sourcePrefix` 内，将工具调用关联到其前一条最近的 text part；无法匹配时显示为 `-`
  - 在聊天和工具两侧互相显示关联关系
- 状态栏指标：
  - System Prompt token 估算（按字符长度粗估）
  - Chat History token 估算（按字符长度粗估）
  - Input / Output / Cache token（读取 `assistant_message.info.tokens`；字段缺失时按 `0` 显示）
  - Turn 持续时间（`started_at` 到 `completed_at`）
- 顶栏信息：
  - 文件名、turn 数量、parse error 数量
  - 自动汇总并展示日志中的 `schema` 列表

## 输入数据约定

每一行应是一个 JSON 对象（非对象会被标记为解析错误）。  
可识别的顶层字段包括（不要求全量存在）：

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

可视化重点会读取：

- `llm_input.system`
- `llm_input.messages[].parts[]`（当前仅消费 `type === "text"` 作为 Chat History）
- `llm_input.user_message.parts[]`（当 `messages` 为空时）
- `llm_output.assistant_message.parts[]`
- `llm_output.assistant_message.info.finish`
- `llm_output.assistant_message.info.tokens`
- Tool Invocations 当前主要来自 `llm_output.assistant_message.parts[]` 中 `type === "tool"`；当 `messages` 为空时，额外读取 `llm_input.user_message.parts[]` 中的 `tool`

## JSONL 示例（单行一个 JSON）

```json
{"schema":"opencode.llm.turn.v1","session_id":"s-001","turn_id":"t-001","turn_index":1,"started_at":"2026-03-04T10:00:00Z","completed_at":"2026-03-04T10:00:02Z","llm_input":{"system":["You are a helpful assistant."],"messages":[{"info":{"role":"user"},"parts":[{"type":"text","text":"帮我查一下订单 1001"}]}]},"llm_output":{"assistant_message":{"info":{"finish":"stop","tokens":{"input":120,"output":38,"cache":{"read":0,"write":0}}},"parts":[{"type":"text","text":"我先调用工具查询订单。"},{"type":"tool","tool":"get_order","callID":"call_abc123","state":{"status":"completed","input":{"order_id":"1001"},"output":{"id":"1001","status":"paid"}}}]}}}
```

## 快速开始

```bash
cd visualizer
npm install
npm run dev
```

开发服务器启动后，在浏览器打开 Vite 输出的本地地址（通常是 `http://localhost:5173`）。

## 构建与预览

```bash
cd visualizer
npm run build
npm run preview
```

## 日志生成（opencode + plugins）

JSONL 日志不是由 `visualizer` 生成，而是通过 `opencode` + 本仓库 `plugins/` 生成。

1. 将本仓库里的 `plugins/` 文件夹拷贝到：
   - `C:\Users\你的用户名\.config\opencode\`
2. 打开并使用 `opencode`，在你要工作的项目目录中进行对话/调用。
3. `opencode` 会在该工作目录下自动创建 `logs/` 文件夹。
4. `logs/` 中的 `*.jsonl` 文件即为可导入 `visualizer` 的日志文件。

示例（目录关系）：

```text
你的项目目录/
├─ logs/
│  ├─ session-001.jsonl
│  └─ session-002.jsonl
└─ ...其他项目文件
```

## 目录说明

```text
.
├─ logs/                # 日志目录（可存放 *.jsonl）
├─ plugins/             # 其他插件代码（不影响 visualizer 启动）
├─ specs/               # 设计文档
└─ visualizer/          # 可视化前端
   ├─ src/
   │  ├─ App.tsx
   │  ├─ parser.ts
   │  ├─ types.ts
   │  ├─ utils.ts
   │  └─ components/
   ├─ styles/
   └─ package.json
```

## 使用流程

1. 先按“日志生成（opencode + plugins）”步骤生成 `logs/*.jsonl`。
2. 启动 `visualizer`。
3. 点击 `Open JSONL` 导入文件。
4. 在左侧筛选并选择 Turn。
5. 在右侧查看 System / Chat / Tool 详情与指标。
6. 如有解析异常，可展开 `Parse Errors` 定位具体行。

## 当前限制

- 仅支持本地文件导入，不包含后端服务。
- `llm_input.messages[].parts[]` 当前仅展示 `type === "text"`，不会将其中的 `tool` part 计入 Tool Invocations 面板。
- 时间字段通过 `toLocaleString()` 按浏览器本地时区显示，可能与日志中的原始 ISO/UTC 表达不同。
- token 估算值为近似值，仅用于快速对比，不等同于模型真实计费 token。
