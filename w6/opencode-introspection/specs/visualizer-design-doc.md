# JSONL Conversation Visualizer Design Doc

## 1. Background & Goal
We have conversation turn logs in `./logs/*.jsonl`.  
Each line is one JSON object (`opencode.llm.turn.v1`), containing a full turn-level snapshot:
- LLM input (`llm_input`)
- LLM output (`llm_output`)
- turn metadata (IDs, timestamps, index)

Goal: build a React app under `./visualizer` so users can open a JSONL file and browse turns clearly in one page, with:
- strong categorization per turn
- constrained scrollable regions
- markdown rendering for textual content
- visual style based on existing design token/global css

---

## 2. Observed Schema (from current `./logs`)

### 2.1 Top-level record
Stable fields observed:
- `schema` (`opencode.llm.turn.v1`)
- `session_id`
- `turn_id`
- `turn_index`
- `user_message_id`
- `assistant_message_id`
- `started_at`
- `completed_at`
- `llm_input`
- `llm_output`

### 2.2 `llm_input`
Observed fields:
- `model` (`providerID`, `modelID`, `raw`)
- `provider` (provider info + models map)
- `agent` (agent config/prompt/permissions)
- `user_message` (`info` + `parts`)
- `messages` (optional conversation snapshot array)
- `system` (optional array of prompt fragments)
- `params` (model params/options)
- `headers`
- `capture_meta`

### 2.3 `llm_output`
Observed fields:
- `assistant_message` with:
  - `info` (role, finish, tokens, etc.)
  - `parts` (union-like array)

Observed `parts[].type`:
- `text`
- `tool`
- `step-start`
- `step-finish`

---

## 3. Product Scope

### In Scope
- Single-page app to open one JSONL file at a time.
- Parse line-by-line JSON.
- Left navigation for turns.
- Right details panel for selected turn:
  - Overview
  - Input section
  - Output section
  - Raw JSON section
- Markdown rendering for textual blocks (system prompts, user text parts, assistant text/tool textual output).
- Scrollbars on long regions (turn list, system/messages/parts/raw).

### Out of Scope
- Editing logs.
- Multi-file merge/compare.
- Backend APIs.
- Authentication/permissions.

---

## 4. UX / Information Architecture

## 4.1 Main layout
- Top bar:
  - file picker button
  - current file name
  - parsing stats (total turns / errors)
  - quick schema badge
- Body split (desktop):
  - Left column: turn list
  - Right column: turn details for selected turn
- Mobile/tablet:
  - stacked layout (list first, details second)

## 4.2 Turn list (left)
Each row shows:
- `turn_index`
- assistant finish reason
- start/end time (short)
- turn/assistant ids (truncated)

List is scrollable with fixed max height (`calc(100vh - header)` style).

## 4.3 Turn detail (right)
Tabbed details:
- `Overview`
- `LLM Input`
- `LLM Output`
- `Raw`

Subsections use cards and internal scroll containers:
- Long JSON blocks: monospace + overflow auto
- Long markdown text: bounded block with scrollbar

---

## 5. Technical Design

## 5.1 App architecture
- React + Vite + TypeScript
- Pure client-side parsing
- Dependencies:
  - `react`, `react-dom`
  - `react-markdown`, `remark-gfm`

## 5.2 Data model
Core internal types:
- `TurnRecord`
- `MessageLike` (`info`, `parts`)
- `Part` union with safe fallback as `Record<string, unknown>`

Parser output:
- `records: TurnRecord[]`
- `parseErrors: { line: number; message: string }[]`
- normalized + sorted by `turn_index`

## 5.3 Parsing strategy
- Split file by newline
- Ignore empty lines
- `JSON.parse` per line with try/catch
- Keep successfully parsed records even if some lines fail
- Show parse errors in UI (top summary + collapsible panel)

## 5.4 Rendering strategy
- Markdown renderer for all textual content:
  - string fields in text parts
  - system prompt blocks
  - tool output when string
- Non-text objects:
  - pretty JSON (`JSON.stringify(..., null, 2)`)
  - in `<pre>` blocks with scrollbar

## 5.5 Scroll/length control
- Turn list: fixed-height scroll container
- Input `system/messages`: fixed max-height containers
- Output `parts`: fixed max-height container
- Raw JSON tab: fixed max-height + horizontal scrollbar for wide lines

---

## 6. Styling & Tokens
- Keep existing style assets in `./visualizer/styles`.
- Ensure app uses:
  - token file: `./visualizer/styles/design-token.css` (required by task)
  - global file: `./visualizer/styles/global.css`

Implementation note:
- Current repository has `design-tokens.css` (plural).
- Add alias file `design-token.css` that imports `design-tokens.css`.
- Update `global.css` import to use `design-token.css`.

---

## 7. File Plan

Will create:
- `visualizer/package.json`
- `visualizer/index.html`
- `visualizer/tsconfig.json`
- `visualizer/vite.config.ts`
- `visualizer/src/main.tsx`
- `visualizer/src/App.tsx`
- `visualizer/src/types.ts`
- `visualizer/src/parser.ts`
- `visualizer/src/components/*`
- `visualizer/src/app.css`
- `visualizer/styles/design-token.css` (alias)
- adjust `visualizer/styles/global.css` import line

---

## 8. Verification Plan
- Type check/build via `npm run build` under `./visualizer`.
- Manual runtime checks:
  - open existing `./logs/*.jsonl` file
  - verify turns render and can switch
  - verify markdown rendering appears in text/system/tool outputs
  - verify long sections show internal scrollbar (not full-page overflow)
  - verify parse errors panel works with malformed sample

