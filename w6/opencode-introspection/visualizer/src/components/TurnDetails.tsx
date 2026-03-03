import { ReactNode, useEffect, useState } from "react";
import { ParsedTurn } from "../types";
import { asArray, asNumber, asObject, asString, formatIsoTime, truncate } from "../utils";
import { JsonBlock } from "./JsonBlock";
import { MarkdownBlock } from "./MarkdownBlock";

interface TurnDetailsProps {
  turn: ParsedTurn | null;
  selectedTurnOrder: number;
  totalTurns: number;
  hasPrev: boolean;
  hasNext: boolean;
  onPrev: () => void;
  onNext: () => void;
}

interface ChatEntry {
  id: string;
  role: string;
  source: string;
  sourcePrefix: string;
  partIndex: number;
  partType: string;
  text: string | null;
  raw: unknown;
}

interface ToolInvocation {
  id: string;
  source: string;
  sourcePrefix: string;
  partIndex: number;
  role: string;
  toolName: string;
  callId: string;
  status: string;
  input: unknown;
  output: unknown;
}

type SectionKey = "system" | "chat" | "tool";

interface EntryCollapseController {
  isExpanded: (entryId: string, defaultExpanded: boolean) => boolean;
  toggle: (entryId: string) => void;
}

interface ChatToolLinks {
  chatToToolIds: Record<string, string[]>;
  toolToChatId: Record<string, string>;
}

interface CollapsibleEntryCardProps {
  className: string;
  entryId: string;
  header: ReactNode;
  body: ReactNode;
  expanded: boolean;
  onToggle: () => void;
}

function CollapsibleEntryCard({
  className,
  entryId,
  header,
  body,
  expanded,
  onToggle
}: CollapsibleEntryCardProps) {
  return (
    <article className={`viz-entry-card ${className} ${expanded ? "" : "is-collapsed"}`.trim()}>
      <button
        type="button"
        className="viz-entry-toggle"
        onClick={onToggle}
        aria-expanded={expanded}
        aria-controls={`${entryId}-content`}
      >
        <header className="viz-entry-head">{header}</header>
        <span className="viz-entry-toggle-meta">
          <span className="viz-entry-toggle-icon" aria-hidden="true">
            {expanded ? "-" : "+"}
          </span>
        </span>
      </button>

      {expanded ? (
        <div id={`${entryId}-content`} className="viz-entry-content">
          {body}
        </div>
      ) : null}
    </article>
  );
}

function estimateTokens(text: string): number {
  if (!text.trim()) {
    return 0;
  }
  return Math.max(1, Math.round(text.length / 4));
}

function estimateTokensFromUnknown(value: unknown): number {
  if (typeof value === "string") {
    return estimateTokens(value);
  }
  return estimateTokens(JSON.stringify(value ?? ""));
}

function toChatEntries(parts: unknown[], role: string, sourcePrefix: string): ChatEntry[] {
  const entries: Array<ChatEntry | null> = parts.map((part, index) => {
      const partObject = asObject(part);
      const partType = asString(partObject?.type) ?? "unknown";
      if (partType !== "text") {
        return null;
      }

      const text = asString(partObject?.text);
      if (!text || !text.trim()) {
        return null;
      }

      return {
        id: `${sourcePrefix}-${index}-${partType}`,
        role,
        source: `${sourcePrefix}.parts[${index}]`,
        sourcePrefix,
        partIndex: index,
        partType,
        text,
        raw: partObject ?? part
      };
    });

  return entries.filter((entry): entry is ChatEntry => entry !== null);
}

function toToolInvocations(parts: unknown[], role: string, sourcePrefix: string): ToolInvocation[] {
  const entries: Array<ToolInvocation | null> = parts.map((part, index) => {
      const partObject = asObject(part);
      if (asString(partObject?.type) !== "tool") {
        return null;
      }

      const state = asObject(partObject?.state);
      return {
        id: `${sourcePrefix}-tool-${index}`,
        source: `${sourcePrefix}.parts[${index}]`,
        sourcePrefix,
        partIndex: index,
        role,
        toolName: asString(partObject?.tool) ?? "unknown",
        callId: asString(partObject?.callID) ?? "-",
        status: asString(state?.status) ?? "-",
        input: state?.input ?? null,
        output: state?.output ?? null
      };
    });

  return entries.filter((entry): entry is ToolInvocation => entry !== null);
}

function shortCallId(callId: string): string {
  if (!callId || callId === "-") {
    return "-";
  }

  if (callId.length <= 22) {
    return callId;
  }

  return `${callId.slice(0, 22)}...`;
}

function buildChatToolLinks(chatEntries: ChatEntry[], tools: ToolInvocation[]): ChatToolLinks {
  const groupedChats = new Map<string, ChatEntry[]>();
  chatEntries.forEach((entry) => {
    const key = `${entry.role}::${entry.sourcePrefix}`;
    const group = groupedChats.get(key) ?? [];
    group.push(entry);
    groupedChats.set(key, group);
  });

  groupedChats.forEach((group) => {
    group.sort((a, b) => a.partIndex - b.partIndex);
  });

  const chatToToolIds: Record<string, string[]> = {};
  const toolToChatId: Record<string, string> = {};

  tools.forEach((tool) => {
    const key = `${tool.role}::${tool.sourcePrefix}`;
    const chats = groupedChats.get(key) ?? [];

    const calledBy = chats
      .filter((chat) => chat.partIndex < tool.partIndex)
      .sort((a, b) => b.partIndex - a.partIndex)[0];

    if (!calledBy) {
      return;
    }

    toolToChatId[tool.id] = calledBy.id;
    chatToToolIds[calledBy.id] = [...(chatToToolIds[calledBy.id] ?? []), tool.id];
  });

  return { chatToToolIds, toolToChatId };
}

function renderSystemPrompts(
  systemPrompts: unknown[],
  turnLineNumber: number,
  collapse: EntryCollapseController
) {
  if (systemPrompts.length === 0) {
    return <p className="viz-empty-text">No system prompts on this turn.</p>;
  }

  return systemPrompts.map((item, index) => {
    const entryId = `system-${turnLineNumber}-${index}`;

    return (
      <CollapsibleEntryCard
        key={entryId}
        className="viz-entry-card-system"
        entryId={entryId}
        expanded={collapse.isExpanded(entryId, index === 0)}
        onToggle={() => collapse.toggle(entryId)}
        header={<span className="viz-chip">system[{index}]</span>}
        body={typeof item === "string" ? <MarkdownBlock content={item} /> : <JsonBlock data={item} />}
      />
    );
  });
}

function renderChatHistory(
  chatEntries: ChatEntry[],
  turnLineNumber: number,
  collapse: EntryCollapseController,
  toolsById: Record<string, ToolInvocation>,
  chatToToolIds: Record<string, string[]>
) {
  if (chatEntries.length === 0) {
    return <p className="viz-empty-text">No chat history on this turn.</p>;
  }

  return chatEntries.map((entry, index) => {
    const entryId = `chat-${turnLineNumber}-${entry.id}`;
    const calledTools = (chatToToolIds[entry.id] ?? [])
      .map((toolId) => toolsById[toolId])
      .filter((tool): tool is ToolInvocation => Boolean(tool));

    return (
      <CollapsibleEntryCard
        key={entryId}
        className="viz-entry-card-chat"
        entryId={entryId}
        expanded={collapse.isExpanded(entryId, index === 0)}
        onToggle={() => collapse.toggle(entryId)}
        header={
          <>
            <span className="viz-chip">role: {entry.role}</span>
            <span className="viz-chip">type: {entry.partType}</span>
            <span className="viz-chip">{entry.source}</span>
          </>
        }
        body={
          <>
            <div className="viz-cross-links">
              <span className="viz-cross-label">Calls</span>
              {calledTools.length > 0 ? (
                calledTools.map((tool) => (
                  <span className="viz-chip viz-rel-chip" key={`${entry.id}-${tool.id}`}>
                    {tool.toolName} ({shortCallId(tool.callId)})
                  </span>
                ))
              ) : (
                <span className="viz-cross-empty">-</span>
              )}
            </div>
            {entry.text ? <MarkdownBlock content={entry.text} /> : <JsonBlock data={entry.raw} />}
          </>
        }
      />
    );
  });
}

function renderToolInvocations(
  tools: ToolInvocation[],
  turnLineNumber: number,
  collapse: EntryCollapseController,
  chatsById: Record<string, ChatEntry>,
  toolToChatId: Record<string, string>
) {
  if (tools.length === 0) {
    return <p className="viz-empty-text">No tool invocation on this turn.</p>;
  }

  return tools.map((tool, index) => {
    const entryId = `tool-${turnLineNumber}-${tool.id}`;
    const calledBy = chatsById[toolToChatId[tool.id]];

    return (
      <CollapsibleEntryCard
        key={entryId}
        className="viz-entry-card-tool"
        entryId={entryId}
        expanded={collapse.isExpanded(entryId, index === 0)}
        onToggle={() => collapse.toggle(entryId)}
        header={
          <>
            <span className="viz-chip">role: {tool.role}</span>
            <span className="viz-chip">tool: {tool.toolName}</span>
            <span className="viz-chip">status: {tool.status}</span>
            <span className="viz-chip">call: {tool.callId}</span>
          </>
        }
        body={
          <>
            <div className="viz-cross-links">
              <span className="viz-cross-label">Called By</span>
              {calledBy ? (
                <span className="viz-chip viz-rel-chip">
                  {calledBy.role}: {calledBy.source}
                </span>
              ) : (
                <span className="viz-cross-empty">-</span>
              )}
            </div>
            <div className="viz-tool-io">
              <details className="viz-io-fold" open>
                <summary className="viz-io-summary">INPUT</summary>
                <JsonBlock data={tool.input} className="viz-scroll-sm" />
              </details>
              <details className="viz-io-fold" open>
                <summary className="viz-io-summary">OUTPUT</summary>
                {typeof tool.output === "string" ? (
                  <MarkdownBlock content={tool.output} className="viz-scroll-sm" />
                ) : (
                  <JsonBlock data={tool.output} className="viz-scroll-sm" />
                )}
              </details>
            </div>
            <div className="viz-tool-source">{tool.source}</div>
          </>
        }
      />
    );
  });
}

function formatMetric(value: number): string {
  return value.toLocaleString();
}

function formatDuration(start: string | null, end: string | null): string {
  if (!start || !end) {
    return "-";
  }

  const startMs = new Date(start).valueOf();
  const endMs = new Date(end).valueOf();
  if (Number.isNaN(startMs) || Number.isNaN(endMs) || endMs < startMs) {
    return "-";
  }

  return `${((endMs - startMs) / 1000).toFixed(2)}s`;
}

export function TurnDetails({
  turn,
  selectedTurnOrder,
  totalTurns,
  hasPrev,
  hasNext,
  onPrev,
  onNext
}: TurnDetailsProps) {
  const [expandedSections, setExpandedSections] = useState<Record<SectionKey, boolean>>({
    system: true,
    chat: true,
    tool: true
  });
  const [expandedEntries, setExpandedEntries] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setExpandedSections({
      system: true,
      chat: true,
      tool: true
    });
    setExpandedEntries({});
  }, [turn?.lineNumber]);

  const toggleSection = (section: SectionKey) => {
    setExpandedSections((current) => ({
      ...current,
      [section]: !current[section]
    }));
  };
  const isEntryExpanded = (entryId: string, defaultExpanded: boolean) =>
    expandedEntries[entryId] ?? defaultExpanded;
  const toggleEntry = (entryId: string) => {
    setExpandedEntries((current) => ({
      ...current,
      [entryId]: !(current[entryId] ?? true)
    }));
  };

  if (!turn) {
    return (
      <section className="viz-workbench">
        <header className="viz-workbench-header">
          <h2>Turn Details</h2>
        </header>
        <div className="viz-empty-state">No turn selected.</div>
      </section>
    );
  }

  const llmInput = asObject(turn.record.llm_input);
  const llmOutput = asObject(turn.record.llm_output);
  const systemPrompts = asArray(llmInput?.system);
  const inputMessages = asArray(llmInput?.messages);
  const userMessage = asObject(llmInput?.user_message);

  const assistantMessage = asObject(llmOutput?.assistant_message);
  const assistantInfo = asObject(assistantMessage?.info);
  const assistantParts = asArray(assistantMessage?.parts);

  const chatEntries: ChatEntry[] = [];
  const toolEntries: ToolInvocation[] = [];

  if (inputMessages.length === 0) {
    chatEntries.push(...toChatEntries(asArray(userMessage?.parts), "user", "user_message"));
    toolEntries.push(...toToolInvocations(asArray(userMessage?.parts), "user", "user_message"));
  }

  inputMessages.forEach((message, index) => {
    const messageObject = asObject(message);
    const role = asString(asObject(messageObject?.info)?.role) ?? "unknown";
    const parts = asArray(messageObject?.parts);

    chatEntries.push(...toChatEntries(parts, role, `messages[${index}]`));
  });

  chatEntries.push(...toChatEntries(assistantParts, "assistant", "assistant_output"));
  toolEntries.push(...toToolInvocations(assistantParts, "assistant", "assistant_output"));

  const chatsById: Record<string, ChatEntry> = Object.fromEntries(
    chatEntries.map((entry) => [entry.id, entry])
  );
  const toolsById: Record<string, ToolInvocation> = Object.fromEntries(
    toolEntries.map((entry) => [entry.id, entry])
  );
  const links = buildChatToolLinks(chatEntries, toolEntries);

  const tokens = asObject(assistantInfo?.tokens);
  const cache = asObject(tokens?.cache);
  const inputTokens = asNumber(tokens?.input) ?? 0;
  const outputTokens = asNumber(tokens?.output) ?? 0;
  const cacheRead = asNumber(cache?.read) ?? 0;
  const cacheWrite = asNumber(cache?.write) ?? 0;

  const sysPromptTokenEst = systemPrompts.reduce<number>(
    (sum, item) => sum + estimateTokensFromUnknown(item),
    0
  );
  const chatTokenEst = chatEntries.reduce<number>((sum, entry) => {
    if (entry.text) {
      return sum + estimateTokens(entry.text);
    }
    return sum + estimateTokensFromUnknown(entry.raw);
  }, 0);

  const startedAt = asString(turn.record.started_at);
  const completedAt = asString(turn.record.completed_at);
  const duration = formatDuration(startedAt, completedAt);

  return (
    <section className="viz-workbench">
      <header className="viz-workbench-header">
        <div className="viz-workbench-title">
          <div className="viz-workbench-title-row">
            <h2>Turn {selectedTurnOrder}</h2>
            <span>
              {selectedTurnOrder}/{totalTurns} | {truncate(asString(turn.record.turn_id), 88)}
            </span>
            <span>
              {formatIsoTime(startedAt)} - {formatIsoTime(completedAt)}
            </span>
          </div>
        </div>

        <div className="viz-workbench-nav">
          <button type="button" className="viz-nav-btn" onClick={onPrev} disabled={!hasPrev}>
            {"< Back"}
          </button>
          <button type="button" className="viz-nav-btn" onClick={onNext} disabled={!hasNext}>
            {"Fwd >"}
          </button>
        </div>
      </header>

      <div className="viz-workbench-body">
        <section
          className={`viz-pane viz-pane-system ${expandedSections.system ? "" : "is-collapsed"}`}
        >
          <header className="viz-pane-header">
            <button
              type="button"
              className="viz-pane-toggle"
              onClick={() => toggleSection("system")}
              aria-expanded={expandedSections.system}
              aria-controls="viz-pane-system-content"
            >
              <span className="viz-pane-title">System Prompts</span>
              <span className="viz-pane-toggle-meta">
                <span className="viz-chip">{systemPrompts.length}</span>
                <span className="viz-pane-toggle-icon" aria-hidden="true">
                  {expandedSections.system ? "-" : "+"}
                </span>
              </span>
            </button>
          </header>
          {expandedSections.system ? (
            <div id="viz-pane-system-content" className="viz-pane-scroll">
              {renderSystemPrompts(systemPrompts, turn.lineNumber, {
                isExpanded: isEntryExpanded,
                toggle: toggleEntry
              })}
            </div>
          ) : null}
        </section>

        <div className="viz-pane-stack">
          <section
            className={`viz-pane viz-pane-chat ${expandedSections.chat ? "" : "is-collapsed"}`}
          >
            <header className="viz-pane-header">
              <button
                type="button"
                className="viz-pane-toggle"
                onClick={() => toggleSection("chat")}
                aria-expanded={expandedSections.chat}
                aria-controls="viz-pane-chat-content"
              >
                <span className="viz-pane-title">Chat History</span>
                <span className="viz-pane-toggle-meta">
                  <span className="viz-chip">{chatEntries.length}</span>
                  <span className="viz-pane-toggle-icon" aria-hidden="true">
                    {expandedSections.chat ? "-" : "+"}
                  </span>
                </span>
              </button>
            </header>
            {expandedSections.chat ? (
              <div id="viz-pane-chat-content" className="viz-pane-scroll">
                {renderChatHistory(chatEntries, turn.lineNumber, {
                  isExpanded: isEntryExpanded,
                  toggle: toggleEntry
                }, toolsById, links.chatToToolIds)}
              </div>
            ) : null}
          </section>

          <section
            className={`viz-pane viz-pane-tool ${expandedSections.tool ? "" : "is-collapsed"}`}
          >
            <header className="viz-pane-header">
              <button
                type="button"
                className="viz-pane-toggle"
                onClick={() => toggleSection("tool")}
                aria-expanded={expandedSections.tool}
                aria-controls="viz-pane-tool-content"
              >
                <span className="viz-pane-title">Tool Invocations</span>
                <span className="viz-pane-toggle-meta">
                  <span className="viz-chip">{toolEntries.length}</span>
                  <span className="viz-pane-toggle-icon" aria-hidden="true">
                    {expandedSections.tool ? "-" : "+"}
                  </span>
                </span>
              </button>
            </header>
            {expandedSections.tool ? (
              <div id="viz-pane-tool-content" className="viz-pane-scroll">
                {renderToolInvocations(toolEntries, turn.lineNumber, {
                  isExpanded: isEntryExpanded,
                  toggle: toggleEntry
                }, chatsById, links.toolToChatId)}
              </div>
            ) : null}
          </section>
        </div>
      </div>

      <footer className="viz-statusbar" role="status" aria-live="polite">
        <span className="viz-status-item">
          Sysprompt: {formatMetric(sysPromptTokenEst)} tokens
        </span>
        <span className="viz-status-item">
          Chat history: {formatMetric(chatTokenEst)} tokens
        </span>
        <span className="viz-status-divider">|</span>
        <span className="viz-status-item">Input: {formatMetric(inputTokens)}</span>
        <span className="viz-status-item">Output: {formatMetric(outputTokens)}</span>
        <span className="viz-status-item">
          Cache: R:{formatMetric(cacheRead)} W:{formatMetric(cacheWrite)}
        </span>
        <span className="viz-status-item">{duration}</span>
      </footer>
    </section>
  );
}
