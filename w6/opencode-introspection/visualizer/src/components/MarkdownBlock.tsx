import ReactMarkdown, { Components } from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownBlockProps {
  content: string;
  emptyText?: string;
  className?: string;
}

export function MarkdownBlock({
  content,
  emptyText = "No text content.",
  className = ""
}: MarkdownBlockProps) {
  const markdownComponents: Components = {
    a: ({ ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
    img: ({ alt }) => (
      <span className="viz-markdown-image-disabled">[Image omitted in preview] {alt ?? ""}</span>
    )
  };

  const trimmed = content.trim();
  if (!trimmed) {
    return <p className="viz-empty-text">{emptyText}</p>;
  }

  return (
    <div className={`viz-markdown ${className}`.trim()}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {trimmed}
      </ReactMarkdown>
    </div>
  );
}
