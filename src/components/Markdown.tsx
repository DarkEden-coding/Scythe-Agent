import type { ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '../utils/cn';

interface MarkdownProps {
  readonly content: string;
  readonly className?: string;
  readonly renderSpecialLink?: (href: string, children: ReactNode) => ReactNode | null;
}

const baseClass = 'markdown-content max-w-none min-w-0 leading-relaxed text-inherit break-words [&_*]:max-w-full';

function createComponents(renderSpecialLink?: MarkdownProps['renderSpecialLink']): Components {
  return {
  p: ({ children }) => <p className="my-1.5 last:my-0 break-words [overflow-wrap:anywhere]">{children}</p>,
  ul: ({ children }) => <ul className="my-1.5 list-disc pl-5 space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="my-1.5 list-decimal pl-5 space-y-0.5">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  code: ({ className, children, ...props }) => {
    const isBlock = className?.includes('language-');
    if (isBlock) {
      return (
        <pre className="my-2 p-2 rounded-md bg-gray-950/60 overflow-x-hidden border border-gray-700/30 text-[11px] whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
          <code className="font-mono whitespace-pre-wrap break-words [overflow-wrap:anywhere]" {...props}>
            {children}
          </code>
        </pre>
      );
    }
    return (
      <code className="px-1 py-0.5 rounded bg-gray-700/50 font-mono text-[0.9em] break-words [overflow-wrap:anywhere]" {...props}>
        {children}
      </code>
    );
  },
  pre: ({ children }) => <>{children}</>,
  a: ({ href, children }) => {
    if (href && renderSpecialLink) {
      const rendered = renderSpecialLink(href, children);
      if (rendered) return rendered;
    }
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className="text-aqua-400 hover:text-aqua-300 underline">
        {children}
      </a>
    );
  },
  strong: ({ children }) => <strong className="font-semibold text-gray-100">{children}</strong>,
  h1: ({ children }) => <h1 className="text-base font-semibold mt-2 mb-1 first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="text-sm font-semibold mt-2 mb-1 first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-medium mt-1.5 mb-0.5">{children}</h3>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-gray-600 pl-3 my-1.5 text-gray-400 italic">{children}</blockquote>
  ),
  table: ({ children }) => (
    <div className="overflow-x-hidden my-2 max-w-full">
      <table className="border-collapse text-[11px] w-full table-fixed">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-gray-600/50 px-2 py-1 text-left bg-gray-800/50 font-medium">{children}</th>
  ),
  td: ({ children }) => <td className="border border-gray-600/50 px-2 py-1 break-words [overflow-wrap:anywhere]">{children}</td>,
  tr: ({ children }) => <tr>{children}</tr>,
  };
}

export function Markdown({ content, className, renderSpecialLink }: MarkdownProps) {
  return (
    <div className={cn(baseClass, className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={createComponents(renderSpecialLink)}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
