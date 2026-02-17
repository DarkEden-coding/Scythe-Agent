import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '../utils/cn';

interface MarkdownProps {
  readonly content: string;
  readonly className?: string;
}

const baseClass = 'markdown-content max-w-none leading-relaxed text-inherit';

const components = {
  p: ({ children }) => <p className="my-1.5 last:my-0">{children}</p>,
  ul: ({ children }) => <ul className="my-1.5 list-disc pl-5 space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="my-1.5 list-decimal pl-5 space-y-0.5">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  code: ({ className, children, ...props }) => {
    const isBlock = className?.includes('language-');
    if (isBlock) {
      return (
        <pre className="my-2 p-2 rounded-md bg-gray-950/60 overflow-x-auto border border-gray-700/30 text-[11px]">
          <code className="font-mono" {...props}>
            {children}
          </code>
        </pre>
      );
    }
    return (
      <code className="px-1 py-0.5 rounded bg-gray-700/50 font-mono text-[0.9em]" {...props}>
        {children}
      </code>
    );
  },
  pre: ({ children }) => <>{children}</>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-aqua-400 hover:text-aqua-300 underline">
      {children}
    </a>
  ),
  strong: ({ children }) => <strong className="font-semibold text-gray-100">{children}</strong>,
  h1: ({ children }) => <h1 className="text-base font-semibold mt-2 mb-1 first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="text-sm font-semibold mt-2 mb-1 first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-medium mt-1.5 mb-0.5">{children}</h3>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-gray-600 pl-3 my-1.5 text-gray-400 italic">{children}</blockquote>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-2">
      <table className="border-collapse text-[11px]">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-gray-600/50 px-2 py-1 text-left bg-gray-800/50 font-medium">{children}</th>
  ),
  td: ({ children }) => <td className="border border-gray-600/50 px-2 py-1">{children}</td>,
  tr: ({ children }) => <tr>{children}</tr>,
};

export function Markdown({ content, className }: MarkdownProps) {
  return (
    <div className={cn(baseClass, className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
