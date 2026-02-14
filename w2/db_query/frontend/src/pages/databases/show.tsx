import { Alert, Button, Empty, Space, Typography } from "antd";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { SchemaViewer } from "../../components/SchemaViewer";
import { apiClient } from "../../services/api";
import type { DatabaseConnection, SchemaMetadata } from "../../types/models";

export function DatabasesShowPage() {
  const params = useParams();
  const dbName = params.id;

  const [connection, setConnection] = useState<DatabaseConnection | null>(null);
  const [metadata, setMetadata] = useState<SchemaMetadata | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDetail = useCallback(async () => {
    if (!dbName) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const detail = await apiClient.getDatabase(dbName);
      setConnection(detail.connection);
      setMetadata(detail.metadata);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load database details");
    } finally {
      setLoading(false);
    }
  }, [dbName]);

  const refreshMetadata = async () => {
    if (!dbName) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const next = await apiClient.refreshDatabase(dbName);
      setMetadata(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh metadata");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  if (!dbName) {
    return <Empty description="Database name is missing in URL" />;
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Space style={{ justifyContent: "space-between", width: "100%" }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Database: {dbName}
        </Typography.Title>
        <Space>
          <Button onClick={refreshMetadata} loading={loading}>
            Refresh Metadata
          </Button>
          <Link to={`/query?db=${encodeURIComponent(dbName)}`}>
            <Button type="primary">Open Query</Button>
          </Link>
        </Space>
      </Space>

      {error ? <Alert type="error" message={error} /> : null}

      {!connection && !loading ? (
        <Empty description="Connection not found" />
      ) : (
        <div>
          <Typography.Paragraph>
            URL: <Typography.Text code>{connection?.url ?? "-"}</Typography.Text>
          </Typography.Paragraph>
          <SchemaViewer metadata={metadata} />
        </div>
      )}
    </Space>
  );
}
