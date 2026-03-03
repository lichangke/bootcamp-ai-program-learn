import { useMemo, useState } from "react";
import { ParsedTurn } from "../types";
import { asNumber, asObject, asString, formatIsoTime, truncate } from "../utils";

interface TurnListProps {
  title: string;
  turns: ParsedTurn[];
  selectedLineNumber: number | null;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onSelect: (lineNumber: number) => void;
}

function getFinishReason(turn: ParsedTurn): string {
  const llmOutput = asObject(turn.record.llm_output);
  const assistantMessage = asObject(llmOutput?.assistant_message);
  const info = asObject(assistantMessage?.info);
  return asString(info?.finish) ?? "-";
}

function getOutputTokens(turn: ParsedTurn): number | null {
  const llmOutput = asObject(turn.record.llm_output);
  const assistantMessage = asObject(llmOutput?.assistant_message);
  const info = asObject(assistantMessage?.info);
  const tokens = asObject(info?.tokens);
  return asNumber(tokens?.output);
}

export function TurnList({
  title,
  turns,
  selectedLineNumber,
  collapsed,
  onToggleCollapse,
  onSelect
}: TurnListProps) {
  const [keyword, setKeyword] = useState<string>("");

  const filteredTurns = useMemo(() => {
    const query = keyword.trim().toLowerCase();
    if (!query) {
      return turns;
    }

    return turns.filter((turn) => {
      const turnIndex = asNumber(turn.record.turn_index);
      const turnId = asString(turn.record.turn_id);
      const userId = asString(turn.record.user_message_id);
      const assistantId = asString(turn.record.assistant_message_id);
      const finishReason = getFinishReason(turn);

      const text = [
        turnIndex !== null ? String(turnIndex) : "",
        turnId ?? "",
        userId ?? "",
        assistantId ?? "",
        finishReason
      ]
        .join(" ")
        .toLowerCase();

      return text.includes(query);
    });
  }, [keyword, turns]);

  return (
    <aside className={`viz-turn-rail ${collapsed ? "is-collapsed" : ""}`}>
      <header className="viz-turn-rail-header">
        <div>
          <h2>{collapsed ? "T" : "Turns"}</h2>
          {!collapsed ? <p title={title}>{truncate(title, 34)}</p> : null}
        </div>
        <button type="button" className="viz-collapse-btn" onClick={onToggleCollapse}>
          {collapsed ? ">>" : "<<"}
        </button>
      </header>

      {!collapsed ? (
        <div className="viz-turn-filter">
          <input
            className="md-input"
            placeholder="Search turn/index/id/status..."
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
          />
          <span className="viz-turn-count">{filteredTurns.length}/{turns.length}</span>
        </div>
      ) : null}

      <div className="viz-turn-list">
        {filteredTurns.map((turn) => {
          const turnIndex = asNumber(turn.record.turn_index);
          const startedAt = asString(turn.record.started_at);
          const finishReason = getFinishReason(turn);
          const outTokens = getOutputTokens(turn);
          const selected = turn.lineNumber === selectedLineNumber;

          return (
            <button
              type="button"
              key={turn.lineNumber}
              className={`viz-turn-row ${selected ? "is-selected" : ""}`}
              onClick={() => onSelect(turn.lineNumber)}
              title={asString(turn.record.turn_id) ?? ""}
            >
              <span className="viz-turn-index">
                {turnIndex !== null ? `#${turnIndex}` : `L${turn.lineNumber}`}
              </span>
              {!collapsed ? (
                <>
                  <span className="viz-turn-finish">{finishReason}</span>
                  <span className="viz-turn-time">{formatIsoTime(startedAt)}</span>
                  <span className="viz-turn-token">
                    out: {outTokens === null ? "-" : outTokens.toLocaleString()}
                  </span>
                </>
              ) : null}
            </button>
          );
        })}
      </div>
    </aside>
  );
}
