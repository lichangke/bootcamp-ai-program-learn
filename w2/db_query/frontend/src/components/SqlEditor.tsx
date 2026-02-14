import Editor from "@monaco-editor/react";

interface SqlEditorProps {
  value: string;
  onChange: (value: string) => void;
  height?: string;
}

export function SqlEditor({ value, onChange, height = "260px" }: SqlEditorProps) {
  return (
    <Editor
      height={height}
      defaultLanguage="sql"
      language="sql"
      value={value}
      options={{
        minimap: { enabled: false },
        wordWrap: "on",
        quickSuggestions: true,
      }}
      onChange={(nextValue) => onChange(nextValue ?? "")}
    />
  );
}

