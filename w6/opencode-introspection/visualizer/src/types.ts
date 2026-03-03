export type JsonObject = Record<string, unknown>;

export interface TurnRecord extends JsonObject {
  schema?: string;
  session_id?: string;
  turn_id?: string;
  turn_index?: number | string;
  user_message_id?: string;
  assistant_message_id?: string;
  started_at?: string;
  completed_at?: string;
  llm_input?: JsonObject;
  llm_output?: JsonObject;
}

export interface ParsedTurn {
  lineNumber: number;
  record: TurnRecord;
}

export interface ParseError {
  lineNumber: number;
  message: string;
  source: string;
}

export interface ParseResult {
  records: ParsedTurn[];
  parseErrors: ParseError[];
}

export type DetailTab = "overview" | "llm-input" | "llm-output" | "raw";
