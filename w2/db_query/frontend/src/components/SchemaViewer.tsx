import { Collapse, Empty, Table, Typography } from "antd";

import type { ColumnMetadata, SchemaMetadata } from "../types/models";

interface SchemaViewerProps {
  metadata: SchemaMetadata | null;
}

function columnsForTable() {
  return [
    {
      title: "Column",
      dataIndex: "columnName",
      key: "columnName",
    },
    {
      title: "Type",
      dataIndex: "dataType",
      key: "dataType",
    },
    {
      title: "Nullable",
      dataIndex: "isNullable",
      key: "isNullable",
      render: (value: boolean) => (value ? "YES" : "NO"),
    },
  ];
}

function buildRows(columns: ColumnMetadata[]) {
  return columns.map((column) => ({
    key: column.columnName,
    ...column,
  }));
}

export function SchemaViewer({ metadata }: SchemaViewerProps) {
  if (!metadata) {
    return <Empty description="No schema metadata available" />;
  }

  const items = [...metadata.tables, ...metadata.views].map((table) => ({
    key: `${table.schemaName}.${table.tableName}`,
    label: `${table.schemaName}.${table.tableName} (${table.tableType})`,
    children: (
      <Table
        size="small"
        pagination={false}
        columns={columnsForTable()}
        dataSource={buildRows(table.columns)}
      />
    ),
  }));

  return (
    <div>
      <Typography.Paragraph>
        Database: <Typography.Text strong>{metadata.databaseName}</Typography.Text>
      </Typography.Paragraph>
      {items.length === 0 ? <Empty description="No tables or views found" /> : <Collapse items={items} />}
    </div>
  );
}

