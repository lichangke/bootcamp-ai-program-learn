# db-query (W2)

This folder is the starting point for the Week 2 **DB Query Tool**.

## Non-negotiable constraints (from the project constitution)

- No authentication/authorization (intentionally out of scope)
- Backend CORS allows all origins (assume trusted/local deployment)
- Backend JSON responses use `camelCase` (including errors and nested fields)
- SQL execution is read-only:
  - only `SELECT` is allowed
  - multi-statement input is rejected
  - missing `LIMIT` gets a default `LIMIT 1000`
- Local durable state lives at `~/.db_query/db_query.db` (SQLite)
- OpenAI API key is read from `OPENAI_API_KEY` and MUST NOT be persisted

## Pointers

- Constitution: `.specify/memory/constitution.md`
- W2 instructions (design notes): `specs/w2/instructions.md`
