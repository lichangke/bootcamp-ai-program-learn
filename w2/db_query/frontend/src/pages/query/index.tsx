import { Alert, Button, Empty, Form, Input, Space, Tabs, Typography } from "antd";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { NaturalLanguageInput } from "../../components/NaturalLanguageInput";
import { QueryResults } from "../../components/QueryResults";
import { SqlEditor } from "../../components/SqlEditor";
import { apiClient } from "../../services/api";
import type { QueryResult } from "../../types/models";

interface FormValues {
  dbName: string;
}

const DEFAULT_SQL = "SELECT 1 AS value";

export function QueryPage() {
  const [searchParams] = useSearchParams();
  const initialDbName = useMemo(() => searchParams.get("db") ?? "", [searchParams]);

  const [dbName, setDbName] = useState(initialDbName);
  const [sql, setSql] = useState(DEFAULT_SQL);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [naturalPrompt, setNaturalPrompt] = useState("");
  const [generatingSql, setGeneratingSql] = useState(false);
  const [activeTab, setActiveTab] = useState<"sql" | "natural">("sql");
  const [generatedSqlPreview, setGeneratedSqlPreview] = useState<string | null>(null);

  const onSubmit = async () => {
    if (!dbName.trim()) {
      setError("Database name is required");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const next = await apiClient.executeQuery(dbName.trim(), { sql });
      setResult(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to execute query");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const generateSql = async () => {
    if (!dbName.trim()) {
      setError("Database name is required");
      return;
    }
    if (!naturalPrompt.trim()) {
      setError("Natural language prompt is required");
      return;
    }
    setGeneratingSql(true);
    setError(null);
    setGeneratedSqlPreview(null);
    try {
      const generated = await apiClient.generateSql(dbName.trim(), { prompt: naturalPrompt.trim() });
      setGeneratedSqlPreview(generated.generatedSql);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate SQL");
    } finally {
      setGeneratingSql(false);
    }
  };

  const useGeneratedSql = () => {
    if (!generatedSqlPreview) {
      return;
    }
    setSql(generatedSqlPreview);
    setActiveTab("sql");
  };

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Title level={3} style={{ margin: 0 }}>
        SQL Query
      </Typography.Title>

      <Form<FormValues> layout="vertical" initialValues={{ dbName }}>
        <Form.Item label="Connection Name" required>
          <Input
            value={dbName}
            onChange={(event) => setDbName(event.target.value)}
            placeholder="demo"
          />
        </Form.Item>
      </Form>

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as "sql" | "natural")}
        items={[
          {
            key: "sql",
            label: "SQL",
            children: (
              <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                <SqlEditor value={sql} onChange={setSql} />
                <Button type="primary" onClick={onSubmit} loading={loading}>
                  Run Query
                </Button>
              </Space>
            ),
          },
          {
            key: "natural",
            label: "Natural Language",
            children: (
              <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                <NaturalLanguageInput
                  prompt={naturalPrompt}
                  onPromptChange={setNaturalPrompt}
                  onGenerate={generateSql}
                  loading={generatingSql}
                />
                {generatedSqlPreview ? (
                  <div>
                    <Typography.Text strong>Generated SQL Preview</Typography.Text>
                    <SqlEditor value={generatedSqlPreview} onChange={setGeneratedSqlPreview} height="180px" />
                    <Space style={{ marginTop: 8 }}>
                      <Button type="primary" onClick={useGeneratedSql}>
                        Use Generated SQL
                      </Button>
                      <Button onClick={onSubmit} loading={loading}>
                        Run This Query
                      </Button>
                    </Space>
                  </div>
                ) : null}
              </Space>
            ),
          },
        ]}
      />

      {error ? <Alert type="error" message={error} /> : null}

      {!dbName && !result ? <Empty description="Select or enter a database connection" /> : null}
      <QueryResults result={result} loading={loading} />
    </Space>
  );
}
