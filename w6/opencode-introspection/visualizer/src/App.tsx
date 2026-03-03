import { ChangeEvent, useMemo, useRef, useState } from "react";
import { parseJsonl } from "./parser";
import { ParseError, ParsedTurn } from "./types";
import { asString } from "./utils";
import { TurnDetails } from "./components/TurnDetails";
import { TurnList } from "./components/TurnList";

interface ParseErrorPanelProps {
  parseErrors: ParseError[];
}

function getSchemas(turns: ParsedTurn[]): string[] {
  const allSchemas = turns
    .map((turn) => asString(turn.record.schema))
    .filter((schema): schema is string => Boolean(schema));

  return [...new Set(allSchemas)];
}

function ParseErrorPanel({ parseErrors }: ParseErrorPanelProps) {
  if (parseErrors.length === 0) {
    return null;
  }

  return (
    <details className="viz-parse-errors">
      <summary>Parse Errors ({parseErrors.length})</summary>
      <div className="viz-parse-errors-list">
        {parseErrors.map((error) => (
          <article key={`${error.lineNumber}-${error.message}`} className="viz-parse-error-row">
            <div className="viz-parse-error-meta">
              <span className="viz-chip">line: {error.lineNumber}</span>
              <span>{error.message}</span>
            </div>
            <pre>{error.source}</pre>
          </article>
        ))}
      </div>
    </details>
  );
}

export default function App() {
  const [fileName, setFileName] = useState<string>("");
  const [turns, setTurns] = useState<ParsedTurn[]>([]);
  const [parseErrors, setParseErrors] = useState<ParseError[]>([]);
  const [selectedLineNumber, setSelectedLineNumber] = useState<number | null>(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const schemaList = useMemo(() => getSchemas(turns), [turns]);
  const selectedTurn = useMemo(
    () => turns.find((turn) => turn.lineNumber === selectedLineNumber) ?? null,
    [turns, selectedLineNumber]
  );
  const selectedTurnIndex = useMemo(
    () => turns.findIndex((turn) => turn.lineNumber === selectedLineNumber),
    [turns, selectedLineNumber]
  );

  const hasPrev = selectedTurnIndex > 0;
  const hasNext = selectedTurnIndex >= 0 && selectedTurnIndex < turns.length - 1;

  const handleFileOpen = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const text = await file.text();
    const parsed = parseJsonl(text);

    setFileName(file.name);
    setTurns(parsed.records);
    setParseErrors(parsed.parseErrors);
    setSelectedLineNumber(parsed.records[0]?.lineNumber ?? null);

    event.target.value = "";
  };

  const goToTurnByIndex = (index: number) => {
    const nextTurn = turns[index];
    if (!nextTurn) {
      return;
    }
    setSelectedLineNumber(nextTurn.lineNumber);
  };

  return (
    <div className="viz-app">
      <header className="viz-topbar">
        <div className="viz-topbar-main">
          <h1>OpenCode Turn Visualizer</h1>
          <p>Inspect System Prompts, Chat History, and Tool Invocations per turn.</p>
        </div>
        <div className="viz-topbar-actions">
          <button
            type="button"
            className="md-btn viz-file-button"
            onClick={() => fileInputRef.current?.click()}
          >
            Open JSONL
          </button>
          <input
            ref={fileInputRef}
            id="jsonl-file-input"
            type="file"
            accept=".jsonl,.log,.txt,application/x-ndjson"
            onChange={handleFileOpen}
            className="viz-file-input-sr"
          />
          <span className="viz-file-name">{fileName || "No file selected"}</span>
          <span className="viz-chip">turns: {turns.length}</span>
          <span className="viz-chip">errors: {parseErrors.length}</span>
          {schemaList.map((schema) => (
            <span className="viz-chip" key={schema}>
              {schema}
            </span>
          ))}
        </div>
      </header>

      <ParseErrorPanel parseErrors={parseErrors} />

      {turns.length === 0 ? (
        <main className="viz-empty-view">
          <h2>Load a JSONL file</h2>
          <p>
            Open a file from the repository <code>logs/</code> folder to visualize each turn.
          </p>
        </main>
      ) : (
        <main className={`viz-main-layout ${isSidebarCollapsed ? "is-sidebar-collapsed" : ""}`}>
          <TurnList
            title={fileName || "Conversation"}
            turns={turns}
            selectedLineNumber={selectedLineNumber}
            collapsed={isSidebarCollapsed}
            onToggleCollapse={() => setIsSidebarCollapsed((value) => !value)}
            onSelect={(lineNumber) => setSelectedLineNumber(lineNumber)}
          />
          <TurnDetails
            turn={selectedTurn}
            selectedTurnOrder={selectedTurnIndex >= 0 ? selectedTurnIndex + 1 : 0}
            totalTurns={turns.length}
            hasPrev={hasPrev}
            hasNext={hasNext}
            onPrev={() => goToTurnByIndex(selectedTurnIndex - 1)}
            onNext={() => goToTurnByIndex(selectedTurnIndex + 1)}
          />
        </main>
      )}
    </div>
  );
}
