import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  ConfigProvider,
  Empty,
  Form,
  Input,
  Modal,
  Space,
  Table,
  Tabs,
  Tag,
  Tree,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";

import { SqlEditor } from "./components/SqlEditor";
import { apiClient } from "./services/api";
import type {
  DatabaseConnection,
  LlmHealthStatus,
  QueryResult,
  SchemaMetadata,
  TableMetadata,
} from "./types/models";

const DEFAULT_SQL = "SELECT 1 AS value";
const RESIZER_WIDTH = 8;
const SIDEBAR_MIN_WIDTH = 220;
const SIDEBAR_MAX_WIDTH = 520;
const MAIN_MIN_WIDTH = 780;
const SCHEMA_MIN_WIDTH = 260;
const SCHEMA_MAX_WIDTH = 620;
const QUERY_MIN_WIDTH = 520;

interface AddDatabaseFormValues {
  name: string;
  url: string;
}

interface ExplorerNode {
  key: string;
  title: ReactNode;
  children?: ExplorerNode[];
}

interface RowRecord {
  key: string;
  [key: string]: unknown;
}

interface LlmIndicatorState {
  color: "green" | "yellow" | "red";
  label: string;
  description: string;
}

function App() {
  const [messageApi, contextHolder] = message.useMessage();
  const workspaceRootRef = useRef<HTMLDivElement | null>(null);
  const workspaceBodyRef = useRef<HTMLElement | null>(null);

  const [databases, setDatabases] = useState<DatabaseConnection[]>([]);
  const [loadingDatabases, setLoadingDatabases] = useState(false);
  const [selectedDbName, setSelectedDbName] = useState<string | null>(null);
  const [sidebarWidth, setSidebarWidth] = useState(280);
  const [schemaWidth, setSchemaWidth] = useState(320);

  const [metadata, setMetadata] = useState<SchemaMetadata | null>(null);
  const [loadingMetadata, setLoadingMetadata] = useState(false);

  const [sql, setSql] = useState(DEFAULT_SQL);
  const [naturalPrompt, setNaturalPrompt] = useState("");
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [runningQuery, setRunningQuery] = useState(false);
  const [generatingSql, setGeneratingSql] = useState(false);
  const [llmHealth, setLlmHealth] = useState<LlmHealthStatus | null>(null);
  const [checkingLlmHealth, setCheckingLlmHealth] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [searchText, setSearchText] = useState("");

  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [savingDatabase, setSavingDatabase] = useState(false);
  const [addForm] = Form.useForm<AddDatabaseFormValues>();

  const selectedConnection = useMemo(
    () => databases.find((database) => database.name === selectedDbName) ?? null,
    [databases, selectedDbName],
  );

  const loadDatabases = async () => {
    setLoadingDatabases(true);
    try {
      const next = await apiClient.listDatabases();
      setDatabases(next);
      setSelectedDbName((previous) => {
        if (previous && next.some((item) => item.name === previous)) {
          return previous;
        }
        return next[0]?.name ?? null;
      });
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load databases");
    } finally {
      setLoadingDatabases(false);
    }
  };

  const loadDatabaseDetail = async (databaseName: string) => {
    setLoadingMetadata(true);
    try {
      const detail = await apiClient.getDatabase(databaseName);
      setMetadata(detail.metadata);
    } catch (fetchError) {
      setMetadata(null);
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load metadata");
    } finally {
      setLoadingMetadata(false);
    }
  };

  useEffect(() => {
    void loadDatabases();
  }, []);

  useEffect(() => {
    if (!selectedDbName) {
      setMetadata(null);
      return;
    }
    void loadDatabaseDetail(selectedDbName);
  }, [selectedDbName]);

  const refreshMetadata = async () => {
    if (!selectedDbName) {
      return;
    }
    setLoadingMetadata(true);
    setError(null);
    try {
      const next = await apiClient.refreshDatabase(selectedDbName);
      setMetadata(next);
      messageApi.success("Metadata refreshed");
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : "Failed to refresh metadata");
    } finally {
      setLoadingMetadata(false);
    }
  };

  const executeQuery = async () => {
    if (!selectedDbName) {
      setError("Please select a database first");
      return;
    }
    setRunningQuery(true);
    setError(null);
    try {
      const result = await apiClient.executeQuery(selectedDbName, { sql });
      setQueryResult(result);
    } catch (runError) {
      setQueryResult(null);
      setError(runError instanceof Error ? runError.message : "Failed to execute query");
    } finally {
      setRunningQuery(false);
    }
  };

  const generateSql = async () => {
    if (!selectedDbName) {
      setError("Please select a database first");
      return;
    }
    if (!naturalPrompt.trim()) {
      setError("Natural language prompt is required");
      return;
    }
    setGeneratingSql(true);
    setError(null);
    try {
      const generated = await apiClient.generateSql(selectedDbName, {
        prompt: naturalPrompt.trim(),
      });
      setSql(generated.generatedSql);
      messageApi.success("SQL generated");
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "Failed to generate SQL");
    } finally {
      setGeneratingSql(false);
    }
  };

  const checkLlmHealth = async () => {
    setCheckingLlmHealth(true);
    setError(null);
    try {
      const status = await apiClient.getLlmHealth();
      setLlmHealth(status);
      if (status.reachable) {
        messageApi.success("LLM health check passed");
      } else {
        messageApi.warning("LLM health check failed");
      }
    } catch (healthError) {
      const details = healthError instanceof Error ? healthError.message : "Failed to check LLM health";
      setLlmHealth((previous) => ({
        provider: previous?.provider ?? "deepseek",
        model: previous?.model ?? "deepseek-chat",
        baseUrl: previous?.baseUrl ?? "https://api.deepseek.com",
        status: "error",
        reachable: false,
        details,
      }));
      setError(details);
    } finally {
      setCheckingLlmHealth(false);
    }
  };

  const addDatabase = async () => {
    try {
      const values = await addForm.validateFields();
      setSavingDatabase(true);
      await apiClient.upsertDatabase(values.name, { url: values.url });
      setIsAddModalOpen(false);
      addForm.resetFields();
      await loadDatabases();
      setSelectedDbName(values.name);
      setError(null);
      messageApi.success("Database connection saved");
    } catch (saveError) {
      if (saveError instanceof Error) {
        setError(saveError.message);
      }
    } finally {
      setSavingDatabase(false);
    }
  };

  const deleteDatabase = async (databaseName: string) => {
    try {
      await apiClient.deleteDatabase(databaseName);
      if (selectedDbName === databaseName) {
        setSelectedDbName(null);
        setQueryResult(null);
      }
      await loadDatabases();
      setError(null);
      messageApi.success(`Database '${databaseName}' deleted`);
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Failed to delete database");
    }
  };

  const filteredObjects = useMemo(() => {
    if (!metadata) {
      return [];
    }
    const search = searchText.trim().toLowerCase();
    const objects: TableMetadata[] = [...metadata.tables, ...metadata.views];
    if (!search) {
      return objects;
    }
    return objects.filter((item) => {
      const objectName = `${item.schemaName}.${item.tableName}`.toLowerCase();
      if (objectName.includes(search)) {
        return true;
      }
      return item.columns.some((column) => column.columnName.toLowerCase().includes(search));
    });
  }, [metadata, searchText]);

  const schemaTreeData: ExplorerNode[] = useMemo(
    () =>
      filteredObjects.map((table) => ({
        key: `${table.schemaName}.${table.tableName}`,
        title: (
          <Space size={8}>
            <Typography.Text strong>{table.tableName}</Typography.Text>
            <Tag color="blue">{table.tableType}</Tag>
            <Typography.Text type="secondary">{table.columns.length} columns</Typography.Text>
          </Space>
        ),
        children: table.columns.map((column) => ({
          key: `${table.schemaName}.${table.tableName}.${column.columnName}`,
          title: (
            <Space size={6}>
              <Typography.Text>{column.columnName}</Typography.Text>
              <Tag>{column.dataType}</Tag>
              {table.primaryKeys.includes(column.columnName) ? <Tag color="red">PK</Tag> : null}
              {!column.isNullable ? <Tag color="purple">NOT NULL</Tag> : null}
            </Space>
          ),
        })),
      })),
    [filteredObjects],
  );

  const resultColumns = useMemo<ColumnsType<RowRecord>>(() => {
    if (!queryResult) {
      return [];
    }
    return queryResult.columns.map((column) => ({
      title: column.name.toUpperCase(),
      dataIndex: column.name,
      key: column.name,
      ellipsis: true,
    }));
  }, [queryResult]);

  const resultRows = useMemo<RowRecord[]>(() => {
    if (!queryResult) {
      return [];
    }
    return queryResult.rows.map((row, index) => ({ key: String(index), ...row }));
  }, [queryResult]);

  const stats = {
    tables: metadata?.tables.length ?? 0,
    views: metadata?.views.length ?? 0,
    rows: queryResult?.rowCount ?? 0,
    time: queryResult ? `${Math.round(queryResult.executionTime * 1000)}ms` : "--",
  };
  const llmIndicator = getLlmIndicator(llmHealth);

  const exportResult = (kind: "json" | "csv") => {
    if (!queryResult) {
      return;
    }

    const content =
      kind === "json"
        ? JSON.stringify(queryResult.rows, null, 2)
        : buildCsv(queryResult.columns.map((column) => column.name), queryResult.rows);

    const blob = new Blob([content], { type: kind === "json" ? "application/json" : "text/csv" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `query-result.${kind}`;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const startColumnResize = (
    event: React.MouseEvent<HTMLDivElement>,
    options: {
      startWidth: number;
      minWidth: number;
      maxWidth: number;
      updateWidth: (value: number) => void;
    },
  ) => {
    event.preventDefault();

    const startX = event.clientX;
    const { startWidth, minWidth, maxWidth, updateWidth } = options;

    const handleMouseMove = (nextEvent: MouseEvent) => {
      const delta = nextEvent.clientX - startX;
      updateWidth(clamp(startWidth + delta, minWidth, maxWidth));
    };

    const handleMouseUp = () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    };

    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
  };

  const startSidebarResize = (event: React.MouseEvent<HTMLDivElement>) => {
    const containerWidth = workspaceRootRef.current?.getBoundingClientRect().width ?? window.innerWidth;
    const maxWidth = Math.max(
      SIDEBAR_MIN_WIDTH,
      Math.min(SIDEBAR_MAX_WIDTH, containerWidth - MAIN_MIN_WIDTH - RESIZER_WIDTH),
    );

    startColumnResize(event, {
      startWidth: sidebarWidth,
      minWidth: SIDEBAR_MIN_WIDTH,
      maxWidth,
      updateWidth: setSidebarWidth,
    });
  };

  const startSchemaResize = (event: React.MouseEvent<HTMLDivElement>) => {
    const containerWidth = workspaceBodyRef.current?.getBoundingClientRect().width ?? window.innerWidth;
    const maxWidth = Math.max(
      SCHEMA_MIN_WIDTH,
      Math.min(SCHEMA_MAX_WIDTH, containerWidth - QUERY_MIN_WIDTH - RESIZER_WIDTH),
    );

    startColumnResize(event, {
      startWidth: schemaWidth,
      minWidth: SCHEMA_MIN_WIDTH,
      maxWidth,
      updateWidth: setSchemaWidth,
    });
  };

  return (
    <ConfigProvider
      theme={{
        token: {
          borderRadius: 2,
          colorBgContainer: "#f2f2f2",
          colorText: "#2a2a2a",
        },
      }}
    >
      {contextHolder}
      <div
        className="workspace-root"
        ref={workspaceRootRef}
        style={{ gridTemplateColumns: `${sidebarWidth}px ${RESIZER_WIDTH}px minmax(0, 1fr)` }}
      >
        <aside className="workspace-sidebar">
          <div className="sidebar-title">DB QUERY TOOL</div>
          <Button type="primary" className="add-db-button" onClick={() => setIsAddModalOpen(true)}>
            + ADD DATABASE
          </Button>

          <div className="database-list">
            {databases.length === 0 && !loadingDatabases ? <Empty description="No databases" /> : null}
            {databases.map((database) => (
              <div
                key={database.name}
                role="button"
                tabIndex={0}
                className={`database-card ${selectedDbName === database.name ? "selected" : ""}`}
                onClick={() => setSelectedDbName(database.name)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelectedDbName(database.name);
                  }
                }}
              >
                <div className="database-card-header">
                  <span>{database.name.toUpperCase()}</span>
                  <Button
                    size="small"
                    type="text"
                    onClick={(event) => {
                      event.stopPropagation();
                      void deleteDatabase(database.name);
                    }}
                  >
                    ×
                  </Button>
                </div>
                <Typography.Text className="database-url">{database.url}</Typography.Text>
              </div>
            ))}
          </div>
        </aside>

        <div
          className="workspace-resizer"
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize database sidebar"
          onMouseDown={startSidebarResize}
        />

        <main className="workspace-main">
          <section className="top-bar">
            <div className="active-db-name">
              {selectedDbName ? selectedDbName.toUpperCase() : "NO DATABASE SELECTED"}
            </div>
            <Space size="middle">
              <div className="llm-indicator-wrap" title={llmIndicator.description}>
                <span className={`llm-indicator-dot llm-dot-${llmIndicator.color}`} />
                <Typography.Text className="llm-indicator-text">{llmIndicator.label}</Typography.Text>
              </div>
              <Button onClick={checkLlmHealth} loading={checkingLlmHealth}>
                LLM HEALTH
              </Button>
              <Button onClick={refreshMetadata} loading={loadingMetadata} disabled={!selectedDbName}>
                REFRESH
              </Button>
            </Space>
          </section>

          <section className="stat-grid">
            <StatCard title="TABLES" value={String(stats.tables)} />
            <StatCard title="VIEWS" value={String(stats.views)} />
            <StatCard title="ROWS" value={String(stats.rows)} />
            <StatCard title="TIME" value={stats.time} />
          </section>

          <section
            className="workspace-body"
            ref={workspaceBodyRef}
            style={{ gridTemplateColumns: `${schemaWidth}px ${RESIZER_WIDTH}px minmax(0, 1fr)` }}
          >
            <Card className="schema-panel" title="SCHEMA">
              <Input
                value={searchText}
                onChange={(event) => setSearchText(event.target.value)}
                placeholder="Search tables, columns..."
              />
              <div className="schema-tree-wrap">
                {schemaTreeData.length === 0 ? (
                  <Empty description="No schema loaded" />
                ) : (
                  <Tree treeData={schemaTreeData} defaultExpandAll />
                )}
              </div>
            </Card>

            <div
              className="workspace-resizer"
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize schema panel"
              onMouseDown={startSchemaResize}
            />

            <div className="query-area">
              <Card
                title="QUERY EDITOR"
                extra={
                  <Button type="primary" onClick={executeQuery} loading={runningQuery} disabled={!selectedConnection}>
                    EXECUTE
                  </Button>
                }
              >
                <Tabs
                  defaultActiveKey="manual"
                  items={[
                    {
                      key: "manual",
                      label: "MANUAL SQL",
                      children: <SqlEditor value={sql} onChange={setSql} height="220px" />,
                    },
                    {
                      key: "natural",
                      label: "NATURAL LANGUAGE",
                      children: (
                        <Space direction="vertical" style={{ width: "100%" }}>
                          <Input.TextArea
                            rows={6}
                            value={naturalPrompt}
                            onChange={(event) => setNaturalPrompt(event.target.value)}
                            placeholder="Describe the SQL you want to generate (PostgreSQL/MySQL)..."
                          />
                          <Button onClick={generateSql} loading={generatingSql} disabled={!selectedConnection}>
                            GENERATE SQL
                          </Button>
                        </Space>
                      ),
                    },
                  ]}
                />
              </Card>

              <Card
                title={
                  <Space>
                    <span>RESULTS</span>
                    {queryResult ? (
                      <Typography.Text type="secondary">
                        {queryResult.rowCount} rows - {Math.round(queryResult.executionTime * 1000)}ms
                      </Typography.Text>
                    ) : null}
                  </Space>
                }
                extra={
                  <Space>
                    <Button size="small" onClick={() => exportResult("csv")} disabled={!queryResult}>
                      EXPORT CSV
                    </Button>
                    <Button size="small" onClick={() => exportResult("json")} disabled={!queryResult}>
                      EXPORT JSON
                    </Button>
                  </Space>
                }
              >
                {queryResult ? (
                  <Table<RowRecord>
                    size="small"
                    columns={resultColumns}
                    dataSource={resultRows}
                    pagination={{ pageSize: 50 }}
                    scroll={{ x: true }}
                  />
                ) : (
                  <Empty description="Run a query to see results" />
                )}
              </Card>
            </div>
          </section>

          {error ? <Alert type="error" message={error} showIcon closable onClose={() => setError(null)} /> : null}
        </main>
      </div>

      <Modal
        title="Add Database Connection"
        open={isAddModalOpen}
        onCancel={() => setIsAddModalOpen(false)}
        onOk={() => void addDatabase()}
        confirmLoading={savingDatabase}
      >
        <Form<AddDatabaseFormValues> form={addForm} layout="vertical">
          <Form.Item
            name="name"
            label="Connection Name"
            rules={[
              { required: true, message: "Connection name is required" },
              { pattern: /^[a-zA-Z0-9-]+$/, message: "Only letters, numbers and dashes are allowed" },
            ]}
          >
            <Input placeholder="employees" />
          </Form.Item>
          <Form.Item
            name="url"
            label="Database URL (PostgreSQL or MySQL)"
            rules={[{ required: true, message: "Database URL is required" }]}
          >
            <Input placeholder="postgres://user:pass@host:5432/db or mysql://user:pass@host:3306/db" />
          </Form.Item>
        </Form>
      </Modal>
    </ConfigProvider>
  );
}

function clamp(value: number, minValue: number, maxValue: number): number {
  return Math.max(minValue, Math.min(maxValue, value));
}

function getLlmIndicator(llmHealth: LlmHealthStatus | null): LlmIndicatorState {
  if (!llmHealth) {
    return {
      color: "yellow",
      label: "LLM UNCHECKED",
      description: "LLM health has not been checked yet.",
    };
  }

  if (llmHealth.reachable) {
    return {
      color: "green",
      label: `LLM OK ${llmHealth.latencyMs ?? "-"}ms`,
      description: `Provider: ${llmHealth.provider} · Model: ${llmHealth.model} · Base: ${llmHealth.baseUrl}`,
    };
  }

  if (llmHealth.status === "missing_api_key") {
    return {
      color: "yellow",
      label: "LLM NO KEY",
      description: "Missing DEEPSEEK_API_KEY. Configure key and retry.",
    };
  }

  return {
    color: "red",
    label: "LLM ERROR",
    description: llmHealth.details ?? "LLM probe failed.",
  };
}

function StatCard({ title, value }: { title: string; value: string }) {
  return (
    <Card className="stat-card">
      <Typography.Text className="stat-title">{title}</Typography.Text>
      <Typography.Title level={3} className="stat-value">
        {value}
      </Typography.Title>
    </Card>
  );
}

function buildCsv(columns: string[], rows: Record<string, unknown>[]): string {
  const header = columns.join(",");
  const values = rows.map((row) =>
    columns
      .map((column) => {
        const rawValue = row[column];
        const stringValue = rawValue === null || rawValue === undefined ? "" : String(rawValue);
        if (stringValue.includes(",") || stringValue.includes('"') || stringValue.includes("\n")) {
          return `"${stringValue.replaceAll('"', '""')}"`;
        }
        return stringValue;
      })
      .join(","),
  );
  return [header, ...values].join("\n");
}

export default App;
