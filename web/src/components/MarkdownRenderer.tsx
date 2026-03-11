import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className = "" }: MarkdownRendererProps) {
  return (
    <div className={`prose prose-sm prose-invert max-w-none ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ ...props }) => <a target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300" {...props} />,
          pre: ({ ...props }) => <pre className="bg-slate-900 border border-slate-800 rounded-lg p-4 custom-scrollbar" {...props} />,
          code: ({ ...props }) => <code className="bg-slate-800 rounded px-1.5 py-0.5 text-blue-300 text-[0.9em]" {...props} />
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
