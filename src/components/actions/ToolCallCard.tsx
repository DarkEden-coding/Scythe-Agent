import {
  FileCode,
  FolderOpen,
  Package,
  Hammer,
  Pencil,
  Trash2,
  Plus,
  Terminal,
  Cpu,
  ChevronDown,
  ChevronRight,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
} from 'lucide-react';
import type { ToolCall } from '@/types';
import { cn } from '@/utils/cn';
import { formatToolDisplayName } from '@/utils/tools';

function safeStr(v: unknown): string {
  if (typeof v === 'string') return v;
  if (v == null) return '';
  return typeof v === 'object' ? JSON.stringify(v).slice(0, 50) : JSON.stringify(v);
}

export const toolIcons: Record<string, React.ReactNode> = {
  spawn_sub_agent: <Cpu className="w-3.5 h-3.5" />,
  read_file: <FileCode className="w-3.5 h-3.5" />,
  create_file: <Plus className="w-3.5 h-3.5" />,
  edit_file: <Pencil className="w-3.5 h-3.5" />,
  delete_file: <Trash2 className="w-3.5 h-3.5" />,
  list_files: <FolderOpen className="w-3.5 h-3.5" />,
  execute_command: <Terminal className="w-3.5 h-3.5" />,
  install_npm_packages: <Package className="w-3.5 h-3.5" />,
  build_project: <Hammer className="w-3.5 h-3.5" />,
};

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Clock className="w-3 h-3 text-gray-500" />,
  running: <Loader2 className="w-3 h-3 text-aqua-400 animate-spin" />,
  completed: <CheckCircle2 className="w-3 h-3 text-emerald-400" />,
  error: <XCircle className="w-3 h-3 text-red-400" />,
};

export { statusIcons };

interface ToolCallCardProps {
  readonly call: ToolCall;
  readonly isInParallel?: boolean;
  readonly isExpanded: boolean;
  readonly onToggle: () => void;
}

export function ToolCallCard({
  call,
  isInParallel = false,
  isExpanded,
  onToggle,
}: ToolCallCardProps) {
  let pathHint: string | null = null;
  if (call.input?.path) pathHint = safeStr(call.input.path);
  else if (call.input?.command) pathHint = safeStr(call.input.command).slice(0, 40);
  else if (call.input?.packages) pathHint = `[${(call.input.packages as string[]).length} pkgs]`;
  if (pathHint === '0') pathHint = null;

  const outputLines = (call.output ?? '').split('\n').length;

  return (
    <div className="flex flex-col items-center animate-fade-in-subtle">
      <button
        type="button"
        className={cn(
          'inline-flex items-center gap-1.5 rounded-lg overflow-hidden transition-colors cursor-pointer',
          isInParallel
            ? 'bg-gray-800/30 hover:bg-gray-800/60'
            : 'bg-gray-800/40 border border-gray-700/30 hover:bg-gray-800/60',
        )}
        onClick={onToggle}
      >
        <div className="inline-flex items-center gap-1.5 px-2 py-1.5">
          <span className="text-gray-600 shrink-0">
            {isExpanded ? <ChevronDown className="w-2.5 h-2.5" /> : <ChevronRight className="w-2.5 h-2.5" />}
          </span>
          <span className="text-aqua-400 shrink-0">
            {toolIcons[call.name] || <FileCode className="w-3.5 h-3.5" />}
          </span>
          <span className="text-[11px] text-gray-300 font-mono whitespace-nowrap" title={call.name}>
            {formatToolDisplayName(call.name)}
          </span>
          {pathHint && call.name !== 'build_project' && call.name !== 'list_files' && (
            <span className="text-[10px] text-gray-600 font-mono whitespace-nowrap">{pathHint}</span>
          )}
          {(call.status === 'completed' || call.status === 'error') && outputLines > 0 && (
            <span className="text-[10px] text-gray-600 font-mono whitespace-nowrap">
              lines: {outputLines}
            </span>
          )}
          {call.status === 'running' && (
            <span className="shrink-0 text-aqua-400" title="In progress">
              <Loader2 className="w-3 h-3 animate-spin" />
            </span>
          )}
          {(call.status === 'completed' || call.status === 'error') && typeof call.duration === 'number' && (
            <span className="text-[10px] text-gray-600 font-mono whitespace-nowrap" title="Latency">
              {call.duration}ms
            </span>
          )}
          {(call.status === 'pending' || call.status === 'completed' || call.status === 'error') && (
            <span className="shrink-0">{statusIcons[call.status]}</span>
          )}
        </div>
      </button>

      {call.status === 'error' && call.output && (
        <div className="mt-1 w-full max-w-full rounded-lg border border-red-500/40 bg-red-950/30 overflow-hidden">
          <div className="px-2.5 py-2">
            <span className="text-[10px] uppercase tracking-wider text-red-400 font-medium">Error</span>
            <pre className="mt-1 text-[11px] text-red-300/90 bg-red-950/50 p-2 rounded-md overflow-x-auto border border-red-500/20 font-mono whitespace-pre-wrap break-all">
              {call.output}
            </pre>
          </div>
        </div>
      )}
      {isExpanded && (
        <div className="mt-1 w-full max-w-full rounded-lg border border-gray-700/20 bg-gray-900/50 overflow-hidden">
          <div className="px-2.5 py-2 space-y-2">
            <div>
              <span className="text-[10px] uppercase tracking-wider text-gray-600 font-medium">Input</span>
              <pre className="mt-1 text-[11px] text-gray-400 bg-gray-950/50 p-2 rounded-md overflow-x-auto border border-gray-700/20 font-mono whitespace-pre-wrap break-all">
                {JSON.stringify(call.input, null, 2)}
              </pre>
            </div>
            {call.output && call.status !== 'error' && (
              <div>
                <span className="text-[10px] uppercase tracking-wider text-gray-600 font-medium">Output</span>
                <pre className="mt-1 text-[11px] text-gray-400 bg-gray-950/50 p-2 rounded-md overflow-x-auto border border-gray-700/20 font-mono whitespace-pre-wrap break-all">
                  {call.output}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
