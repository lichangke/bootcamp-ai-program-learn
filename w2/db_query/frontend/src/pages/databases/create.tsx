import { Alert, Button, Form, Input, Space, Typography } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiClient } from "../../services/api";

interface FormValues {
  name: string;
  url: string;
}

export function DatabasesCreatePage() {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const onFinish = async (values: FormValues) => {
    setSubmitting(true);
    setError(null);
    try {
      await apiClient.upsertDatabase(values.name, { url: values.url });
      navigate(`/databases/${values.name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save database connection");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Title level={3} style={{ margin: 0 }}>
        Add Database Connection
      </Typography.Title>
      {error ? <Alert type="error" message={error} /> : null}
      <Form<FormValues> layout="vertical" onFinish={onFinish}>
        <Form.Item
          name="name"
          label="Connection Name"
          rules={[{ required: true, message: "Connection name is required" }]}
        >
          <Input placeholder="production" />
        </Form.Item>
        <Form.Item
          name="url"
          label="Database URL (PostgreSQL or MySQL)"
          rules={[{ required: true, message: "Database URL is required" }]}
        >
          <Input placeholder="postgres://user:pass@host:5432/db or mysql://user:pass@host:3306/db" />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={submitting}>
            Save Connection
          </Button>
        </Form.Item>
      </Form>
    </Space>
  );
}
