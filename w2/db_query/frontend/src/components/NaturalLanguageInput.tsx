import { Button, Form, Input, Space } from "antd";

interface NaturalLanguageInputProps {
  prompt: string;
  loading?: boolean;
  onPromptChange: (value: string) => void;
  onGenerate: () => void;
}

export function NaturalLanguageInput({
  prompt,
  loading = false,
  onPromptChange,
  onGenerate,
}: NaturalLanguageInputProps) {
  return (
    <Form layout="vertical">
      <Form.Item label="Natural Language Prompt" required>
        <Input.TextArea
          value={prompt}
          onChange={(event) => onPromptChange(event.target.value)}
          rows={4}
          placeholder="e.g. show top 10 active users created in the last 30 days"
        />
      </Form.Item>
      <Space>
        <Button onClick={onGenerate} loading={loading} type="primary">
          Generate SQL
        </Button>
      </Space>
    </Form>
  );
}

