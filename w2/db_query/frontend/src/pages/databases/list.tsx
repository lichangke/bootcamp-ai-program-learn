import { Alert, Button, Space, Typography } from "antd";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { DatabaseList } from "../../components/DatabaseList";
import { apiClient } from "../../services/api";
import type { DatabaseConnection } from "../../types/models";

export function DatabasesListPage() {
  const [databases, setDatabases] = useState<DatabaseConnection[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDatabases = async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await apiClient.listDatabases();
      setDatabases(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load databases");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchDatabases();
  }, []);

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Space style={{ justifyContent: "space-between", width: "100%" }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Databases
        </Typography.Title>
        <Link to="/databases/create">
          <Button type="primary">Add Database</Button>
        </Link>
      </Space>
      {error ? <Alert type="error" message={error} /> : null}
      <DatabaseList databases={databases} loading={loading} onRefresh={fetchDatabases} />
    </Space>
  );
}

