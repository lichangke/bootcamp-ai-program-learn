import { Button, Empty, List, Space, Tag, Typography } from "antd";
import { Link } from "react-router-dom";

import type { DatabaseConnection } from "../types/models";

interface DatabaseListProps {
  databases: DatabaseConnection[];
  loading?: boolean;
  onRefresh: () => void;
}

function statusColor(status: DatabaseConnection["status"]): string {
  if (status === "active") {
    return "green";
  }
  if (status === "error") {
    return "red";
  }
  return "default";
}

export function DatabaseList({ databases, loading = false, onRefresh }: DatabaseListProps) {
  if (databases.length === 0 && !loading) {
    return <Empty description="No database connections yet" />;
  }

  return (
    <List
      loading={loading}
      dataSource={databases}
      renderItem={(db) => (
        <List.Item
          actions={[
            <Link key="show" to={`/databases/${db.name}`}>
              View
            </Link>,
            <Link key="query" to={`/query?db=${encodeURIComponent(db.name)}`}>
              Query
            </Link>,
          ]}
        >
          <List.Item.Meta
            title={
              <Space>
                <Typography.Text strong>{db.name}</Typography.Text>
                <Tag color={statusColor(db.status)}>{db.status}</Tag>
              </Space>
            }
            description={db.url}
          />
        </List.Item>
      )}
      footer={
        <Button onClick={onRefresh} disabled={loading}>
          Refresh List
        </Button>
      }
    />
  );
}

