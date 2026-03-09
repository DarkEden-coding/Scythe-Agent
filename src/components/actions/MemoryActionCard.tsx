import { Brain, CheckCircle2, ChevronDown, ChevronRight, Clock, Loader2, XCircle } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { ToolCall } from '@/types';
import { cn } from '@/utils/cn';

function getMemoryTitle(call: ToolCall): string {
  if (call.name === 'write_memory' && typeof call.input?.title === 'string' && call.input.title.trim()) {
    return call.input.title;
  }

  const titles = call.input?.titles;
  if (call.name === 'read_memory' && Array.isArray(titles)) {
    const namedTitles = titles.filter((title): title is string => typeof title === 'string' && title.trim().length > 0);
    if (namedTitles.length === 0) return 'Available memories';
    if (namedTitles.length === 1) return namedTitles[0];
    return `${namedTitles[0]} +${namedTitles.length - 1}`;
  }

  return call.name === 'write_memory' ? 'Project memory' : 'Project memories';
}

function getStatusIcon(call: ToolCall): React.ReactNode {
  if (call.status === 'running') return <Loader2 className="w-3 h-3 text-aqua-300 animate-spin" />;
  if (call.status === 'completed') return <CheckCircle2 className="w-3 h-3 text-emerald-400" />;
  if (call.status === 'error') return <XCircle className="w-3 h-3 text-red-400" />;
  return <Clock className="w-3 h-3 text-gray-500" />;
}

export function MemoryActionCard({ call }: { readonly call: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const title = useMemo(() => getMemoryTitle(call), [call]);
  const label = call.name === 'write_memory' ? 'Saved memory' : 'Read memory';

  return (
    <div className="inline-flex max-w-full flex-col overflow-hidden rounded-xl border border-aqua-500/20 bg-aqua-500/5">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-aqua-500/10"
      >
        <span className="text-aqua-300/70 shrink-0">
          {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        </span>
        <Brain className="w-3.5 h-3.5 shrink-0 text-aqua-300" />
        <div className="min-w-0 flex-1">
          <div className="text-[11px] font-medium text-aqua-200">{label}</div>
          <div className="truncate text-[10px] text-aqua-100/70" title={title}>
            {title}
          </div>
        </div>
        {typeof call.duration === 'number' && (
          <span className="text-[9px] font-mono text-aqua-200/50">{call.duration}ms</span>
        )}
        <span className="shrink-0">{getStatusIcon(call)}</span>
      </button>

      {expanded && (
        <div className="border-t border-aqua-500/15 px-3 py-2">
          <div className="rounded-lg border border-aqua-500/15 bg-gray-950/30 p-2">
            <div className="text-[10px] uppercase tracking-wider text-aqua-300/70">Details</div>
            <pre
              className={cn(
                'mt-1 whitespace-pre-wrap break-all font-mono text-[11px] text-gray-300',
                !call.output && 'text-gray-500',
              )}
            >
              {call.output || JSON.stringify(call.input, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
