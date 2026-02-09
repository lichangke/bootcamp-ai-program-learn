# Research: 数据库查询工具

**Feature**: 002-db-query-tool
**Date**: 2026-02-09
**Purpose**: Research technical decisions and best practices for implementation

## Overview

This document captures research findings for key technical decisions in the database query tool implementation.

## 1. SQL Parsing with sqlglot

### Decision

Use **sqlglot** for SQL parsing, validation, and manipulation.

### Rationale

- **Comprehensive SQL Support**: sqlglot supports multiple SQL dialects including PostgreSQL
- **AST-based Parsing**: Provides abstract syntax tree for analyzing query structure
- **Statement Type Detection**: Can identify SELECT vs INSERT/UPDATE/DELETE statements
- **Query Manipulation**: Can programmatically add LIMIT clauses to queries
- **Pure Python**: No external dependencies, easy to integrate with FastAPI
- **Active Maintenance**: Well-maintained library with good documentation

### Alternatives Considered

1. **sqlparse**: Simpler but less powerful, doesn't provide AST, harder to detect statement types reliably
2. **pglast**: PostgreSQL-specific, uses libpg_query, more accurate but adds C dependency
3. **pyparsing**: Would require writing custom grammar, significant development effort

### Implementation Approach

```python
import sqlglot
from sqlglot import parse_one, exp

def validate_query(sql: str) -> tuple[bool, str]:
    """Validate SQL is SELECT-only and single statement."""
    try:
        # Parse SQL
        statements = sqlglot.parse(sql, dialect="postgres")

        # Check single statement
        if len(statements) != 1:
            return False, "Multiple statements not allowed"

        # Check SELECT only
        stmt = statements[0]
        if not isinstance(stmt, exp.Select):
            return False, "Only SELECT statements allowed"

        return True, ""
    except Exception as e:
        return False, f"SQL syntax error: {str(e)}"

def add_limit_if_missing(sql: str, default_limit: int = 1000) -> str:
    """Add LIMIT clause if not present."""
    stmt = parse_one(sql, dialect="postgres")
    if isinstance(stmt, exp.Select) and not stmt.args.get("limit"):
        stmt = stmt.limit(default_limit)
    return stmt.sql(dialect="postgres")
```

## 2. PostgreSQL Metadata Extraction

### Decision

Use **psycopg2** with PostgreSQL system catalogs (information_schema) to extract metadata.

### Rationale

- **Standard Approach**: information_schema is ANSI SQL standard, portable
- **Comprehensive**: Provides table, view, column, and constraint information
- **Reliable**: Built into PostgreSQL, no additional dependencies
- **Type Information**: Includes data types, nullability, defaults

### Implementation Approach

```python
import psycopg2
from typing import List, Dict

def fetch_database_metadata(connection_url: str) -> Dict:
    """Fetch all tables, views, and columns from database."""
    conn = psycopg2.connect(connection_url)
    cursor = conn.cursor()

    # Get tables and views
    cursor.execute("""
        SELECT
            table_schema,
            table_name,
            table_type
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name
    """)
    tables = cursor.fetchall()

    # Get columns for each table
    metadata = {}
    for schema, table, table_type in tables:
        cursor.execute("""
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (schema, table))

        columns = cursor.fetchall()
        metadata[f"{schema}.{table}"] = {
            "type": table_type,
            "columns": [
                {
                    "name": col[0],
                    "dataType": col[1],
                    "nullable": col[2] == "YES",
                    "default": col[3]
                }
                for col in columns
            ]
        }

    cursor.close()
    conn.close()
    return metadata
```

### Alternatives Considered

1. **SQLAlchemy Reflection**: More abstraction but heavier dependency
2. **Direct pg_catalog queries**: More powerful but PostgreSQL-specific
3. **asyncpg**: Async support but adds complexity for this use case

## 3. OpenAI SDK Integration for Natural Language SQL

### Decision

Use **OpenAI Python SDK** with GPT-4 for natural language to SQL generation.

### Rationale

- **Official SDK**: Well-maintained, type-safe, follows best practices
- **Structured Outputs**: Supports JSON mode for reliable SQL generation
- **Context Management**: Easy to include database schema in prompts
- **Error Handling**: Built-in retry logic and error handling

### Implementation Approach

```python
from openai import OpenAI
import os
import json

def generate_sql_from_natural_language(
    prompt: str,
    schema_metadata: Dict,
    connection_name: str
) -> str:
    """Generate SQL from natural language using OpenAI."""
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Format schema for context
    schema_context = json.dumps(schema_metadata, indent=2)

    system_prompt = f"""You are a SQL expert. Generate PostgreSQL SELECT queries based on user requests.

Database Schema:
{schema_context}

Rules:
- Only generate SELECT statements
- Use proper table and column names from the schema
- Include appropriate WHERE, JOIN, and ORDER BY clauses as needed
- Return only the SQL query, no explanations
"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,  # Low temperature for consistent output
        max_tokens=500
    )

    return response.choices[0].message.content.strip()
```

### Alternatives Considered

1. **Anthropic Claude**: Similar capabilities but OpenAI more established for SQL
2. **Local LLM (Llama)**: No API costs but requires local GPU, less accurate
3. **Rule-based NLP**: Limited flexibility, high maintenance

## 4. FastAPI camelCase JSON Serialization

### Decision

Use **Pydantic alias_generator** with FastAPI to automatically convert snake_case to camelCase.

### Rationale

- **Automatic Conversion**: No manual field mapping needed
- **Type Safety**: Maintains Pydantic validation
- **Bidirectional**: Works for both request and response models
- **Constitution Compliant**: Ensures all JSON uses camelCase

### Implementation Approach

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class CamelCaseModel(BaseModel):
    """Base model with camelCase serialization."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,  # Allow both snake_case and camelCase input
        from_attributes=True
    )

# Example usage
class DatabaseConnection(CamelCaseModel):
    connection_name: str  # Serializes as "connectionName"
    connection_url: str   # Serializes as "connectionUrl"
    created_at: str       # Serializes as "createdAt"
```

### Alternatives Considered

1. **Manual Field Aliases**: More control but error-prone and verbose
2. **Custom JSON Encoder**: Works but bypasses Pydantic validation
3. **Middleware Transformation**: Possible but adds complexity

## 5. Monaco Editor Integration in React

### Decision

Use **@monaco-editor/react** wrapper for Monaco Editor integration.

### Rationale

- **Official React Wrapper**: Maintained by Monaco team
- **SQL Language Support**: Built-in SQL syntax highlighting
- **Autocomplete**: Can be extended with custom completions
- **Lightweight**: Lazy loads Monaco, good performance
- **TypeScript Support**: Full type definitions

### Implementation Approach

```typescript
import Editor from '@monaco-editor/react';
import { useRef } from 'react';

interface SqlEditorProps {
  value: string;
  onChange: (value: string) => void;
  schema?: Record<string, any>;
}

export const SqlEditor: React.FC<SqlEditorProps> = ({
  value,
  onChange,
  schema
}) => {
  const editorRef = useRef(null);

  const handleEditorDidMount = (editor: any, monaco: any) => {
    editorRef.current = editor;

    // Register SQL autocomplete with schema
    if (schema) {
      monaco.languages.registerCompletionItemProvider('sql', {
        provideCompletionItems: () => {
          const suggestions = Object.keys(schema).map(tableName => ({
            label: tableName,
            kind: monaco.languages.CompletionItemKind.Class,
            insertText: tableName,
          }));
          return { suggestions };
        }
      });
    }
  };

  return (
    <Editor
      height="400px"
      language="sql"
      value={value}
      onChange={(value) => onChange(value || '')}
      onMount={handleEditorDidMount}
      theme="vs-dark"
      options={{
        minimap: { enabled: false },
        fontSize: 14,
        lineNumbers: 'on',
        scrollBeyondLastLine: false,
      }}
    />
  );
};
```

### Alternatives Considered

1. **CodeMirror**: Good alternative but Monaco has better SQL support
2. **Ace Editor**: Older, less maintained
3. **Plain textarea**: No syntax highlighting or autocomplete

## 6. Refine 5 Patterns for CRUD Operations

### Decision

Use **Refine 5** with Ant Design for database connection management UI.

### Rationale

- **CRUD Scaffolding**: Automatic list, create, edit, show pages
- **Data Provider Pattern**: Clean separation of API logic
- **Ant Design Integration**: Pre-built components for forms and tables
- **TypeScript First**: Excellent type safety
- **Routing**: Built-in routing with React Router

### Implementation Approach

```typescript
import { Refine } from "@refinedev/core";
import { RefineKbar, RefineKbarProvider } from "@refinedev/kbar";
import routerBindings from "@refinedev/react-router-v6";
import dataProvider from "@refinedev/simple-rest";
import { BrowserRouter } from "react-router-dom";

const API_URL = "http://localhost:8000/api/v1";

function App() {
  return (
    <BrowserRouter>
      <RefineKbarProvider>
        <Refine
          dataProvider={dataProvider(API_URL)}
          routerProvider={routerBindings}
          resources={[
            {
              name: "dbs",
              list: "/databases",
              create: "/databases/create",
              show: "/databases/show/:id",
              meta: {
                label: "Databases",
              },
            },
          ]}
        >
          {/* Routes */}
        </Refine>
      </RefineKbarProvider>
    </BrowserRouter>
  );
}
```

### Alternatives Considered

1. **React Admin**: Similar but less flexible
2. **Custom CRUD**: More control but significant development time
3. **Ant Design Pro**: More opinionated, heavier

## 7. SQLite Storage for Connection Metadata

### Decision

Use **SQLite** with Python's built-in `sqlite3` module for local storage.

### Rationale

- **No External Dependencies**: Built into Python
- **File-based**: Easy to locate at `~/.db_query/db_query.db`
- **ACID Compliant**: Reliable for connection metadata
- **Simple Schema**: Suitable for small data volumes
- **Cross-platform**: Works on Windows, macOS, Linux

### Schema Design

```sql
CREATE TABLE connections (
    name TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE metadata (
    connection_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    table_type TEXT NOT NULL,
    schema_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (connection_name, table_name),
    FOREIGN KEY (connection_name) REFERENCES connections(name) ON DELETE CASCADE
);
```

### Alternatives Considered

1. **JSON Files**: Simpler but no ACID guarantees, harder to query
2. **PostgreSQL**: Overkill for local metadata storage
3. **Redis**: Requires external service, unnecessary complexity

## Summary

All technical decisions align with the project constitution and support the feature requirements:

- ✅ Type safety through Pydantic and TypeScript
- ✅ camelCase JSON via Pydantic alias_generator
- ✅ Read-only SQL enforcement via sqlglot
- ✅ Local SQLite storage at `~/.db_query/db_query.db`
- ✅ OpenAI API key from environment variable
- ✅ CORS support via FastAPI middleware

Next steps: Proceed to Phase 1 (data-model.md, contracts/, quickstart.md)
