import { prettyJson } from "../utils";

interface JsonBlockProps {
  data: unknown;
  className?: string;
}

export function JsonBlock({ data, className = "" }: JsonBlockProps) {
  return (
    <pre className={`viz-json-block ${className}`.trim()}>{prettyJson(data)}</pre>
  );
}
