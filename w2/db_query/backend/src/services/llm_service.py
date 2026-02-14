from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from openai import OpenAI

from src.models.metadata import SchemaMetadata, TableMetadata


class LlmServiceError(RuntimeError):
    """Raised when LLM SQL generation fails."""


class LlmService:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "deepseek-chat",
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    def _resolve_api_key(self) -> str | None:
        return self._api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")

    def health_probe(self) -> dict[str, str | bool | int]:
        api_key = self._resolve_api_key()
        response: dict[str, str | bool | int] = {
            "provider": "deepseek",
            "model": self._model,
            "baseUrl": self._base_url,
        }

        if not api_key:
            response["status"] = "missing_api_key"
            response["reachable"] = False
            return response

        client = OpenAI(api_key=api_key, base_url=self._base_url)
        started_at = time.perf_counter()
        try:
            completion = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": "Reply with exactly: OK"},
                    {"role": "user", "content": "health check"},
                ],
                temperature=0,
                max_tokens=4,
                timeout=8.0,
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            response["status"] = "error"
            response["reachable"] = False
            response["latencyMs"] = elapsed_ms
            response["details"] = str(exc)
            return response

        content = ""
        if completion.choices:
            content = (completion.choices[0].message.content or "").strip()

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        response["status"] = "ok"
        response["reachable"] = True
        response["latencyMs"] = elapsed_ms
        response["response"] = content
        return response

    def prepare_schema_context(
        self,
        metadata: SchemaMetadata,
        prompt: str,
        limit: int = 10,
    ) -> tuple[list[str], dict[str, TableMetadata], dict[str, Any]]:
        prompt_terms = {term.lower() for term in prompt.replace("_", " ").split() if term.strip()}
        all_items = [*metadata.tables, *metadata.views]

        scored: list[tuple[int, TableMetadata]] = []
        for table in all_items:
            table_key = f"{table.schema_name}.{table.table_name}".lower()
            column_names = {column.column_name.lower() for column in table.columns}
            score = 0

            for term in prompt_terms:
                if term in table_key:
                    score += 4
                if any(term in column_name for column_name in column_names):
                    score += 2

            scored.append((score, table))

        scored.sort(key=lambda pair: (-pair[0], pair[1].schema_name, pair[1].table_name))

        selected = [table for score_value, table in scored if score_value > 0][:limit]
        if not selected:
            selected = all_items[:limit]

        table_names = [f"{table.schema_name}.{table.table_name}" for table in selected]
        schema_context = {
            f"{table.schema_name}.{table.table_name}": table
            for table in selected
        }

        prompt_schema = {
            table_name: {
                "tableType": table.table_type,
                "columns": [
                    {
                        "name": column.column_name,
                        "dataType": column.data_type,
                        "isNullable": column.is_nullable,
                    }
                    for column in table.columns
                ],
                "primaryKeys": table.primary_keys,
            }
            for table_name, table in schema_context.items()
        }

        return table_names, schema_context, prompt_schema

    def generate_sql(
        self,
        *,
        prompt: str,
        connection_name: str,
        schema_prompt_context: dict[str, Any],
    ) -> str:
        if not prompt.strip():
            raise LlmServiceError("Natural language prompt cannot be empty")

        fallback_sql = self._build_fallback_sql(prompt, schema_prompt_context)
        api_key = self._resolve_api_key()
        if not api_key:
            return fallback_sql

        client = OpenAI(api_key=api_key, base_url=self._base_url)

        system_prompt = (
            "You are a PostgreSQL SQL assistant. "
            "Return only one SQL statement and no markdown. "
            "The SQL MUST be a single SELECT statement."
        )
        user_prompt = (
            f"Connection: {connection_name}\n"
            f"Schema:\n{json.dumps(schema_prompt_context, ensure_ascii=False, indent=2)}\n\n"
            f"User request:\n{prompt}\n\n"
            "Return only SQL."
        )

        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=500,
            )
        except Exception:
            return fallback_sql

        content = response.choices[0].message.content if response.choices else None
        if not content:
            return fallback_sql

        sql = content.strip()
        if sql.startswith("```"):
            lines = sql.splitlines()
            if len(lines) >= 2:
                first_line = lines[0].strip().lower()
                last_line = lines[-1].strip()
                if first_line.startswith("```") and last_line == "```":
                    inner_lines = lines[1:-1]
                    sql = "\n".join(inner_lines).strip()

        return sql

    def _build_fallback_sql(self, prompt: str, schema_prompt_context: dict[str, Any]) -> str:
        table_names = list(schema_prompt_context.keys())
        if not table_names:
            return "SELECT table_schema, table_name FROM information_schema.tables LIMIT 1000"

        lower_prompt = prompt.lower()
        selected_table = table_names[0]

        for table_name in table_names:
            plain_name = table_name.split(".")[-1].lower()
            if plain_name in lower_prompt or table_name.lower() in lower_prompt:
                selected_table = table_name
                break

        selected_schema = schema_prompt_context.get(selected_table, {})
        raw_columns = selected_schema.get("columns", [])

        column_names: list[str] = []
        if isinstance(raw_columns, list):
            for column in raw_columns:
                if isinstance(column, dict):
                    name = column.get("name")
                    if isinstance(name, str) and name:
                        column_names.append(name)

        if "count" in lower_prompt:
            base_sql = f"SELECT COUNT(*) AS total_count FROM {selected_table}"
        else:
            matching_columns = [
                column_name
                for column_name in column_names
                if column_name.lower() in lower_prompt
            ]
            if matching_columns:
                projected_columns = ", ".join(matching_columns[:5])
                base_sql = f"SELECT {projected_columns} FROM {selected_table}"
            else:
                base_sql = f"SELECT * FROM {selected_table}"

        limit = self._extract_limit(lower_prompt)
        return f"{base_sql} LIMIT {limit}"

    def _extract_limit(self, lower_prompt: str) -> int:
        matches = re.findall(r"\b(?:top|limit)\s+(\d{1,5})\b", lower_prompt)
        if not matches:
            return 1000
        try:
            parsed = int(matches[-1])
        except ValueError:
            return 1000
        return max(1, min(parsed, 1000))
