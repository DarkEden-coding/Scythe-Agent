import { ChevronDown, ChevronRight, Cpu, Loader2 } from 'lucide-react';
import type { SubAgentRun, ToolCall } from '@/types';
import { ToolCallCard, statusIcons } from './ToolCallCard';

interface SubAgentCardProps {
  readonly run: SubAgentRun;
  readonly isExpanded: boolean;
  readonly onToggle: () => void;
  readonly expandedTools: Set<string>;
  readonly onToggleTool: (id: string) => void;
}

export function SubAgentCard({
  run,
  isExpanded,
  onToggle,
  expandedTools,
  onToggleTool,
}: SubAgentCardProps) {
  const isRunning = run.status === 'running' || run.status === 'pending';
  const displayStatus = run.status === 'max_iterations' ? 'error' : run.status;

  return (
    <div className="flex justify-center">
      <div className="inline-flex flex-col border border-indigo-500/25 rounded-xl overflow-hidden bg-indigo-500/5">
        <button
          type="button"
          onClick={onToggle}
          className="flex items-center gap-2 px-2.5 py-1.5 hover:bg-indigo-500/8 transition-colors"
        >
          <span className="text-indigo-400/60 shrink-0">
            {isExpanded ? (
              <ChevronDown className="w-3 h-3" />
            ) : (
              <ChevronRight className="w-3 h-3" />
            )}
          </span>
          <Cpu className="w-3 h-3 text-indigo-400/70" />
          <span className="text-[10px] text-indigo-300/90 font-medium truncate max-w-[220px]" title={run.task}>
            {run.task}
          </span>
          {run.model && (
            <span className="text-[9px] text-indigo-400/50 font-mono truncate max-w-[100px]">{run.model}</span>
          )}
          {isRunning && (
            <span className="shrink-0 text-indigo-400">
              <Loader2 className="w-3 h-3 animate-spin" />
            </span>
          )}
          {(run.status === 'completed' || run.status === 'error' || run.status === 'max_iterations') && (
            <span className="shrink-0">{statusIcons[displayStatus]}</span>
          )}
          {run.duration != null && (
            <span className="text-[9px] text-indigo-400/50 font-mono">{run.duration}ms</span>
          )}
        </button>
        {isExpanded && (
          <div className="px-2 pb-2 space-y-1 border-t border-indigo-500/15">
            <div className="h-1" />
            {run.toolCalls.length > 0 ? (
              run.toolCalls.map((call: ToolCall) => (
                <ToolCallCard
                  key={call.id}
                  call={call}
                  isInParallel
                  isExpanded={expandedTools.has(call.id)}
                  onToggle={() => onToggleTool(call.id)}
                />
              ))
            ) : (
              <p className="text-[10px] text-gray-500 italic py-1">No tool calls yet</p>
            )}
            {run.output && run.status !== 'running' && (
              <div className="mt-1 rounded-lg border border-indigo-500/15 bg-gray-900/30 p-2">
                <span className="text-[10px] text-indigo-400/70 font-medium">Output</span>
                <pre className="mt-1 text-[10px] text-gray-400 font-mono whitespace-pre-wrap break-all max-h-32 overflow-y-auto">
                  {run.output}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
