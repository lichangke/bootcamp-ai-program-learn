import { Empty, Table, Typography } from "antd";

import type { QueryResult } from "../types/models";

interface QueryResultsProps {
  result: QueryResult | null;
  loading?: boolean;
}

export function QueryResults({ result, loading = false }: QueryResultsProps) {
  if (!result) {
    return <Empty description="Run a query to see results" />;
  }

  if (result.rows.length === 0) {
    return (
      <div>
        <Typography.Paragraph>No rows returned.</Typography.Paragraph>
        <Typography.Text type="secondary">Executed SQL: {result.query}</Typography.Text>
      </div>
    );
  }

  const columns = result.columns.map((column) => ({
    title: `${column.name} (${column.type})`,
    dataIndex: column.name,
    key: column.name,
  }));

  const rows = result.rows.map((row, index) => ({ key: String(index), ...row }));

  return (
    <div>
      <Typography.Paragraph>
        Returned {result.rowCount} rows in {result.executionTime.toFixed(3)}s
      </Typography.Paragraph>
      <Table loading={loading} columns={columns} dataSource={rows} scroll={{ x: true }} />
    </div>
  );
}

