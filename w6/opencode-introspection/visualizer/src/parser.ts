import { ParseResult, ParsedTurn, TurnRecord } from "./types";
import { asNumber, asObject } from "./utils";

function compareTurns(a: ParsedTurn, b: ParsedTurn): number {
  const leftIndex = asNumber(a.record.turn_index);
  const rightIndex = asNumber(b.record.turn_index);

  if (leftIndex !== null && rightIndex !== null && leftIndex !== rightIndex) {
    return leftIndex - rightIndex;
  }

  if (leftIndex !== null && rightIndex === null) {
    return -1;
  }

  if (leftIndex === null && rightIndex !== null) {
    return 1;
  }

  return a.lineNumber - b.lineNumber;
}

export function parseJsonl(content: string): ParseResult {
  const lines = content.split(/\r?\n/);
  const records: ParsedTurn[] = [];
  const parseErrors: ParseResult["parseErrors"] = [];

  lines.forEach((rawLine, lineIndex) => {
    const line = rawLine.trim();
    if (!line) {
      return;
    }

    try {
      const parsed = JSON.parse(line) as unknown;
      const record = asObject(parsed);

      if (!record) {
        parseErrors.push({
          lineNumber: lineIndex + 1,
          message: "Line is valid JSON but not an object.",
          source: rawLine
        });
        return;
      }

      records.push({
        lineNumber: lineIndex + 1,
        record: record as TurnRecord
      });
    } catch (error) {
      parseErrors.push({
        lineNumber: lineIndex + 1,
        message: error instanceof Error ? error.message : "Unknown parse error",
        source: rawLine
      });
    }
  });

  records.sort(compareTurns);

  return { records, parseErrors };
}
