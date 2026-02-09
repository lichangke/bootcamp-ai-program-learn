# Data Model: 数据库查询工具

**Feature**: 002-db-query-tool
**Date**: 2026-02-09
**Purpose**: Define data entities, relationships, and validation rules

## Overview

This document defines the data model for the database query tool, including entities for database connections, schema metadata, queries, and results.

## Entity Definitions

### 1. DatabaseConnection

Represents a saved database connection.

**Attributes**:
- `name` (string, required): Unique identifier for the connection (e.g., "production", "staging")
- `url` (string, required): PostgreSQL connection URL (format: `postgres://user:pass@host:port/dbname`)
- `createdAt` (datetime, required): Timestamp when connection was created
- `updatedAt` (datetime, required): Timestamp when connection was last updated
- `status` (enum, computed): Connection status ("active", "error", "unknown")

**Validation Rules**:
- `name`: 1-50 characters, alphanumeric and hyphens only, must be unique
- `url`: Must be valid PostgreSQL connection URL format
- `createdAt`, `updatedAt`: ISO 8601 format

**Relationships**:
- One-to-many with SchemaMetadata (one connection has many tables/views)

**Storage**: SQLite `connections` table

```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Literal

class DatabaseConnection(CamelCaseModel):
    name: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9-]+$')
    url: str = Field(..., pattern=r'^postgres(ql)?://.*')
    created_at: datetime
    updated_at: datetime
    status: Literal["active", "error", "unknown"] = "unknown"

    @field_validator('url')
    @classmethod
    def validate_postgres_url(cls, v: str) -> str:
        if not v.startswith(('postgres://', 'postgresql://')):
            raise ValueError('URL must be a PostgreSQL connection string')
        return v
```

### 2. SchemaMetadata

Represents the complete schema metadata for a database connection.

**Attributes**:
- `connectionName` (string, required): Reference to DatabaseConnection
- `databaseName` (string, required): Name of the database
- `fetchedAt` (datetime, required): When metadata was fetched
- `tables` (array, required): List of TableMetadata objects
- `views` (array, required): List of TableMetadata objects (views)

**Validation Rules**:
- `connectionName`: Must reference existing connection
- `fetchedAt`: ISO 8601 format
- `tables`, `views`: Can be empty arrays

**Relationships**:
- Many-to-one with DatabaseConnection
- One-to-many with TableMetadata

**Storage**: SQLite `metadata` table (JSON serialized)

```python
from typing import List

class SchemaMetadata(CamelCaseModel):
    connection_name: str
    database_name: str
    fetched_at: datetime
    tables: List['TableMetadata']
    views: List['TableMetadata']
```

### 3. TableMetadata

Represents metadata for a single table or view.

**Attributes**:
- `schemaName` (string, required): Schema name (e.g., "public")
- `tableName` (string, required): Table or view name
- `tableType` (enum, required): "TABLE" or "VIEW"
- `columns` (array, required): List of ColumnMetadata objects
- `primaryKeys` (array, optional): List of primary key column names

**Validation Rules**:
- `tableName`: Non-empty string
- `tableType`: Must be "TABLE" or "VIEW"
- `columns`: Must have at least one column

**Relationships**:
- Many-to-one with SchemaMetadata
- One-to-many with ColumnMetadata

```python
class TableMetadata(CamelCaseModel):
    schema_name: str
    table_name: str
    table_type: Literal["TABLE", "VIEW"]
    columns: List['ColumnMetadata']
    primary_keys: List[str] = Field(default_factory=list)
```

### 4. ColumnMetadata

Represents metadata for a single column.

**Attributes**:
- `columnName` (string, required): Column name
- `dataType` (string, required): PostgreSQL data type (e.g., "integer", "varchar", "timestamp")
- `isNullable` (boolean, required): Whether column accepts NULL values
- `defaultValue` (string, optional): Default value expression
- `maxLength` (integer, optional): Maximum length for character types
- `numericPrecision` (integer, optional): Precision for numeric types

**Validation Rules**:
- `columnName`: Non-empty string
- `dataType`: Non-empty string
- `isNullable`: Boolean

```python
from typing import Optional

class ColumnMetadata(CamelCaseModel):
    column_name: str
    data_type: str
    is_nullable: bool
    default_value: Optional[str] = None
    max_length: Optional[int] = None
    numeric_precision: Optional[int] = None
```

### 5. QueryRequest

Represents a user's query request (SQL or natural language).

**Attributes**:
- `connectionName` (string, required): Target database connection
- `queryType` (enum, required): "sql" or "natural"
- `content` (string, required): SQL query or natural language prompt
- `timestamp` (datetime, required): When query was submitted

**Validation Rules**:
- `connectionName`: Must reference existing connection
- `queryType`: Must be "sql" or "natural"
- `content`: Non-empty string, max 10000 characters
- For SQL queries: Must pass sqlglot validation

**Relationships**:
- Many-to-one with DatabaseConnection

```python
class QueryRequest(CamelCaseModel):
    connection_name: str
    query_type: Literal["sql", "natural"]
    content: str = Field(..., min_length=1, max_length=10000)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### 6. QueryResult

Represents the result of a successful query execution.

**Attributes**:
- `columns` (array, required): List of ColumnDefinition objects
- `rows` (array, required): Array of row data (each row is an object)
- `rowCount` (integer, required): Number of rows returned
- `executionTime` (float, required): Query execution time in seconds
- `query` (string, required): The actual SQL that was executed

**Validation Rules**:
- `rowCount`: Must match length of `rows` array
- `executionTime`: Non-negative number
- `rows`: Maximum 1000 rows (enforced by LIMIT)

```python
from typing import Any, Dict

class ColumnDefinition(CamelCaseModel):
    name: str
    type: str

class QueryResult(CamelCaseModel):
    columns: List[ColumnDefinition]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time: float
    query: str

    @field_validator('row_count')
    @classmethod
    def validate_row_count(cls, v: int, info) -> int:
        if 'rows' in info.data and v != len(info.data['rows']):
            raise ValueError('rowCount must match rows array length')
        return v
```

### 7. QueryError

Represents an error that occurred during query processing.

**Attributes**:
- `errorType` (enum, required): Type of error ("connection", "syntax", "validation", "execution", "timeout")
- `errorCode` (string, required): Machine-readable error code
- `message` (string, required): Human-readable error message
- `details` (string, optional): Technical details for debugging
- `query` (string, optional): The query that caused the error

**Validation Rules**:
- `errorType`: Must be one of the defined types
- `message`: Non-empty, user-friendly message
- All fields use camelCase (constitution requirement)

```python
class QueryError(CamelCaseModel):
    error_type: Literal["connection", "syntax", "validation", "execution", "timeout"]
    error_code: str
    message: str
    details: Optional[str] = None
    query: Optional[str] = None
```

### 8. NaturalLanguageContext

Represents the context used for natural language SQL generation.

**Attributes**:
- `connectionName` (string, required): Target database connection
- `userPrompt` (string, required): User's natural language question
- `relevantTables` (array, required): List of table names relevant to the query
- `schemaContext` (object, required): Subset of schema metadata for relevant tables
- `generatedSql` (string, required): SQL generated by LLM
- `timestamp` (datetime, required): When generation occurred

**Validation Rules**:
- `userPrompt`: Non-empty string
- `generatedSql`: Must be valid SQL (validated by sqlglot)
- `relevantTables`: Can be empty if no tables match

```python
class NaturalLanguageContext(CamelCaseModel):
    connection_name: str
    user_prompt: str
    relevant_tables: List[str]
    schema_context: Dict[str, TableMetadata]
    generated_sql: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

## Entity Relationships

```
DatabaseConnection (1) ----< (N) SchemaMetadata
                   |
                   +----< (N) QueryRequest

SchemaMetadata (1) ----< (N) TableMetadata

TableMetadata (1) ----< (N) ColumnMetadata

QueryRequest (1) ----< (1) QueryResult | QueryError

QueryRequest (1) ----< (0..1) NaturalLanguageContext
```

## State Transitions

### DatabaseConnection Status

```
unknown → active (successful connection test)
unknown → error (connection test failed)
active → error (connection lost)
error → active (connection restored)
```

### Query Processing Flow

```
QueryRequest (sql) → Validation → Execution → QueryResult | QueryError
QueryRequest (natural) → LLM Generation → Validation → (User Approval) → Execution → QueryResult | QueryError
```

## Validation Summary

All entities follow these principles:
- ✅ Use Pydantic for type safety and validation
- ✅ All JSON fields use camelCase (via alias_generator)
- ✅ Required fields explicitly marked
- ✅ Enums for constrained values
- ✅ Field validators for complex rules
- ✅ ISO 8601 for all datetime fields

## Storage Strategy

### SQLite Schema

```sql
-- Connection metadata
CREATE TABLE connections (
    name TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Schema metadata (JSON serialized)
CREATE TABLE metadata (
    connection_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    table_type TEXT NOT NULL,
    schema_json TEXT NOT NULL,  -- JSON serialized TableMetadata
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (connection_name, table_name),
    FOREIGN KEY (connection_name) REFERENCES connections(name) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_metadata_connection ON metadata(connection_name);
CREATE INDEX idx_metadata_type ON metadata(table_type);
```

### JSON Serialization

- All Pydantic models serialize to camelCase JSON automatically
- SQLite stores JSON as TEXT using `model.model_dump_json()`
- Deserialization uses `Model.model_validate_json()`

## Next Steps

See [contracts/openapi.yaml](./contracts/openapi.yaml) for API endpoint definitions using these models.
