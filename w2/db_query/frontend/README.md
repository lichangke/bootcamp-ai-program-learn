# DB Query Frontend

React + TypeScript frontend for the DB Query Tool.

## Stack

- React 19 + TypeScript (strict mode)
- Ant Design
- Monaco Editor
- Vite

## Run Locally

```bash
cd w2/db_query/frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Frontend default URL: `http://127.0.0.1:5173`

## Quality Checks

```bash
cd w2/db_query/frontend
npm run type-check
npm run lint
npm run build
```

## Backend Integration

`vite.config.ts` proxies:

- `/api` -> `http://127.0.0.1:8000`
- `/health` -> `http://127.0.0.1:8000`

So the frontend can call:

- `/api/v1/...` business APIs
- `/health/llm` LLM health probe

## UI Highlights

- Resizable left sidebar and schema panel
- SQL editor + natural language generation tab
- Query result table with CSV/JSON export
- LLM health check button and persistent status indicator
