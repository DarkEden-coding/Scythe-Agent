import { useState } from 'react';
import {
  FileCode,
  FolderOpen,
  Package,
  Hammer,
  Pencil,
  Trash2,
  Plus,
  RotateCcw,
  ChevronDown,
  ChevronRight,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  GitBranch,
  Layers,
  Sparkles,
  ShieldCheck,
  X,
  Check,
  Zap,
} from 'lucide-react';
import { ToolCall, FileEdit, Checkpoint, ReasoningBlock } from '../types';
import { Markdown } from './Markdown';
import { cn } from '../utils/cn';
import type { AutoApproveRule } from '../api';

interface ActionsPanelProps {
  toolCalls: ToolCall[];
  fileEdits: FileEdit[];
  checkpoints: Checkpoint[];
  reasoningBlocks: ReasoningBlock[];
  onRevertFile: (fileEditId: string) => void;
  onRevertCheckpoint: (checkpointId: string) => void;
  onApproveCommand?: (toolCallId: string) => void;
  onRejectCommand?: (toolCallId: string) => void;
  autoApproveRules?: AutoApproveRule[];
  onUpdateAutoApproveRules?: (rules: Omit<AutoApproveRule, 'id' | 'createdAt'>[]) => Promise<void> | void;
}

const toolIcons: Record<string, React.ReactNode> = {
  read_file: <FileCode className="w-3.5 h-3.5" />,
  create_file: <Plus className="w-3.5 h-3.5" />,
  edit_file: <Pencil className="w-3.5 h-3.5" />,
  delete_file: <Trash2 className="w-3.5 h-3.5" />,
  list_files: <FolderOpen className="w-3.5 h-3.5" />,
  install_npm_packages: <Package className="w-3.5 h-3.5" />,
  build_project: <Hammer className="w-3.5 h-3.5" />,
};

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Clock className="w-3 h-3 text-gray-500" />,
  running: <Loader2 className="w-3 h-3 text-aqua-400 animate-spin" />,
  completed: <CheckCircle2 className="w-3 h-3 text-emerald-400" />,
  error: <XCircle className="w-3 h-3 text-red-400" />,
};

type TimelineItem =
  | { type: 'tool'; call: ToolCall }
  | { type: 'parallel'; calls: ToolCall[] }
  | { type: 'file'; edit: FileEdit }
  | { type: 'reasoning'; block: ReasoningBlock }
  | { type: 'reasoning_group'; checkpointId: string; blocks: ReasoningBlock[] };

function DiffPreview({ diff, action }: { diff?: string; action: string }) {
  if (!diff) return null;

  const lines = diff.split('\n');

  return (
    <div className="rounded-lg overflow-hidden border border-gray-700/30 bg-gray-950/70 text-[11px] font-mono leading-relaxed">
      <div className="max-h-[220px] overflow-y-auto">
        {lines.map((line, i) => {
          let bgClass = '';
          let textClass = 'text-gray-500';

          if (line.startsWith('+')) {
            bgClass = 'bg-emerald-500/8';
            textClass = 'text-emerald-300/90';
          } else if (line.startsWith('-')) {
            bgClass = 'bg-red-500/8';
            textClass = 'text-red-300/80';
          } else if (line.startsWith('@@')) {
            bgClass = 'bg-aqua-500/5';
            textClass = 'text-aqua-400/60';
          } else {
            textClass = action === 'create' ? 'text-emerald-300/70' : 'text-gray-500';
            if (action === 'create') bgClass = 'bg-emerald-500/5';
          }

          const prefix = line.startsWith('+') ? '+' : line.startsWith('-') ? '-' : line.startsWith('@@') ? '@' : ' ';
          const content = line.startsWith('+') || line.startsWith('-') ? line.slice(1) : line;

          return (
            <div key={i} className={cn('flex', bgClass)}>
              <span className={cn('w-5 flex-shrink-0 text-center select-none opacity-50', textClass)}>
                {prefix === ' ' ? '' : prefix}
              </span>
              <span className={cn('flex-1 px-2 py-px whitespace-pre', textClass)}>
                {content}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ActionsPanel({
  toolCalls,
  fileEdits,
  checkpoints,
  reasoningBlocks,
  onRevertFile,
  onRevertCheckpoint,
  onApproveCommand,
  onRejectCommand,
  autoApproveRules = [],
  onUpdateAutoApproveRules,
}: ActionsPanelProps) {
  const [expandedTools, setExpandedTools] = useState<Set<string>>(new Set());
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set(fileEdits.map(fe => fe.id)));
  const [expandedReasoning, setExpandedReasoning] = useState<Set<string>>(new Set());
  const [expandedThinkingGroups, setExpandedThinkingGroups] = useState<Set<string>>(new Set());
  const [collapsedCheckpoints, setCollapsedCheckpoints] = useState<Set<string>>(new Set());
  const [expandedParallelGroups, setExpandedParallelGroups] = useState<Set<string>>(new Set());

  const toggleTool = (toolId: string) => {
    const newExpanded = new Set(expandedTools);
    if (newExpanded.has(toolId)) newExpanded.delete(toolId);
    else newExpanded.add(toolId);
    setExpandedTools(newExpanded);
  };

  const toggleFile = (fileId: string) => {
    const newExpanded = new Set(expandedFiles);
    if (newExpanded.has(fileId)) newExpanded.delete(fileId);
    else newExpanded.add(fileId);
    setExpandedFiles(newExpanded);
  };

  const toggleReasoning = (blockId: string) => {
    const newExpanded = new Set(expandedReasoning);
    if (newExpanded.has(blockId)) newExpanded.delete(blockId);
    else newExpanded.add(blockId);
    setExpandedReasoning(newExpanded);
  };

  const toggleThinkingGroup = (checkpointId: string) => {
    const next = new Set(expandedThinkingGroups);
    if (next.has(checkpointId)) next.delete(checkpointId);
    else next.add(checkpointId);
    setExpandedThinkingGroups(next);
  };

  const toggleCheckpointCollapse = (cpId: string) => {
    const newCollapsed = new Set(collapsedCheckpoints);
    if (newCollapsed.has(cpId)) newCollapsed.delete(cpId);
    else newCollapsed.add(cpId);
    setCollapsedCheckpoints(newCollapsed);
  };

  const toggleParallelGroup = (groupKey: string, calls: ToolCall[]) => {
    const newExpanded = new Set(expandedParallelGroups);
    const newExpandedTools = new Set(expandedTools);

    if (newExpanded.has(groupKey)) {
      newExpanded.delete(groupKey);
      calls.forEach(c => newExpandedTools.delete(c.id));
    } else {
      newExpanded.add(groupKey);
      calls.forEach(c => newExpandedTools.add(c.id));
    }

    setExpandedParallelGroups(newExpanded);
    setExpandedTools(newExpandedTools);
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  // Build unified timeline grouped by checkpoint
  const buildTimeline = (): { checkpoint: Checkpoint; items: TimelineItem[] }[] => {
    return checkpoints.map((checkpoint) => {
      const cpToolCalls = toolCalls.filter((tc) => checkpoint.toolCalls.includes(tc.id));
      const cpFileEdits = fileEdits.filter((fe) => fe.checkpointId === checkpoint.id);
      const cpReasoningBlocks = reasoningBlocks.filter(
        (rb) => checkpoint.reasoningBlocks?.includes(rb.id)
      );

      const allItems: { timestamp: number; item: TimelineItem }[] = [];

      // Group parallel tool calls
      const parallelGroups = new Map<string, ToolCall[]>();
      const soloTools: ToolCall[] = [];

      cpToolCalls.forEach((tc) => {
        if (tc.isParallel && tc.parallelGroupId) {
          const group = parallelGroups.get(tc.parallelGroupId) || [];
          group.push(tc);
          parallelGroups.set(tc.parallelGroupId, group);
        } else {
          soloTools.push(tc);
        }
      });

      soloTools.forEach((tc) => {
        allItems.push({ timestamp: tc.timestamp.getTime(), item: { type: 'tool', call: tc } });
      });

      parallelGroups.forEach((calls) => {
        allItems.push({
          timestamp: calls[0].timestamp.getTime(),
          item: { type: 'parallel', calls },
        });
      });

      cpFileEdits.forEach((fe) => {
        allItems.push({ timestamp: fe.timestamp.getTime(), item: { type: 'file', edit: fe } });
      });

      if (cpReasoningBlocks.length > 0) {
        const ts = Math.min(...cpReasoningBlocks.map((rb) => rb.timestamp.getTime()));
        allItems.push({
          timestamp: ts,
          item: { type: 'reasoning_group', checkpointId: checkpoint.id, blocks: cpReasoningBlocks },
        });
      }

      allItems.sort((a, b) => a.timestamp - b.timestamp);

      return { checkpoint, items: allItems.map((a) => a.item) };
    });
  };

  const timeline = buildTimeline();

  const renderToolCall = (call: ToolCall, isInParallel = false) => {
    const isExpanded = expandedTools.has(call.id);

    const pathHint = call.input?.path
      ? `${call.input.path}`
      : call.input?.packages
      ? `[${(call.input.packages as string[]).length} pkgs]`
      : null;

    return (
      <div key={call.id} className="flex flex-col items-center">
        <div
          className={cn(
            'inline-flex items-center gap-1.5 rounded-lg overflow-hidden transition-colors cursor-pointer',
            isInParallel
              ? 'bg-gray-800/30 hover:bg-gray-800/60'
              : 'bg-gray-800/40 border border-gray-700/30 hover:bg-gray-800/60'
          )}
          onClick={() => toggleTool(call.id)}
        >
          <div className="inline-flex items-center gap-1.5 px-2 py-1.5">
            <span className="text-gray-600 flex-shrink-0">
              {isExpanded ? <ChevronDown className="w-2.5 h-2.5" /> : <ChevronRight className="w-2.5 h-2.5" />}
            </span>
            <span className="text-aqua-400 flex-shrink-0">{toolIcons[call.name] || <FileCode className="w-3.5 h-3.5" />}</span>
            <span className="text-[11px] text-gray-300 font-mono whitespace-nowrap">{call.name}</span>
            {pathHint && call.name !== 'build_project' && call.name !== 'list_files' && (
              <span className="text-[10px] text-gray-600 font-mono whitespace-nowrap">{pathHint}</span>
            )}
            {call.duration && (
              <span className="text-[10px] text-gray-600 font-mono whitespace-nowrap">{formatDuration(call.duration)}</span>
            )}
            <span className="flex-shrink-0">{statusIcons[call.status]}</span>
          </div>
        </div>

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
  };

  const renderReasoningBlock = (block: ReasoningBlock, compact = true) => {
    const isExpanded = expandedReasoning.has(block.id);
    const previewText = block.content.split('\n')[0].slice(0, compact ? 40 : 60).trim() || '…';

    return (
      <div key={block.id} className="flex flex-col">
        <button
          onClick={() => toggleReasoning(block.id)}
          className={cn(
            'flex items-center gap-1.5 text-left w-full rounded-md px-2 py-1 transition-colors',
            'hover:bg-purple-500/[0.06] border border-transparent hover:border-purple-500/15'
          )}
        >
          <span className="text-purple-400/60 flex-shrink-0">
            {isExpanded ? <ChevronDown className="w-2.5 h-2.5" /> : <ChevronRight className="w-2.5 h-2.5" />}
          </span>
          <Sparkles className="w-2.5 h-2.5 text-purple-400/50 flex-shrink-0" />
          <span className="text-[10px] text-purple-300/60 font-mono truncate flex-1">{previewText}</span>
          {block.duration && (
            <span className="text-[9px] text-purple-400/30 font-mono whitespace-nowrap">{formatDuration(block.duration)}</span>
          )}
        </button>
        {isExpanded && (
          <div className="mt-1 ml-5 pl-2 border-l border-purple-500/15 text-[10px] text-purple-200/50 leading-relaxed max-h-[200px] overflow-y-auto">
            <Markdown content={block.content} className="text-[10px] text-purple-200/50" />
          </div>
        )}
      </div>
    );
  };

  const renderThinkingGroup = (checkpointId: string, blocks: ReasoningBlock[]) => {
    const isGroupExpanded = expandedThinkingGroups.has(checkpointId);

    return (
      <div key={`thinking-${checkpointId}`} className="flex justify-center">
        <div
          className={cn(
            'rounded-lg border transition-all overflow-hidden',
            'border-purple-500/15 bg-purple-500/[0.03] hover:bg-purple-500/[0.06]',
            isGroupExpanded ? 'w-[92%]' : 'inline-flex'
          )}
        >
          <button
            onClick={() => toggleThinkingGroup(checkpointId)}
            className="flex items-center gap-1.5 px-2 py-1.5 w-full min-w-0"
          >
            <span className="text-purple-400/60 flex-shrink-0">
              {isGroupExpanded ? <ChevronDown className="w-2.5 h-2.5" /> : <ChevronRight className="w-2.5 h-2.5" />}
            </span>
            <Sparkles className="w-2.5 h-2.5 text-purple-400/50 flex-shrink-0" />
            <span className="text-[10px] text-purple-300/70 font-medium whitespace-nowrap">
              Thinking · {blocks.length} {blocks.length === 1 ? 'thought' : 'thoughts'}
            </span>
          </button>
          {isGroupExpanded && (
            <div className="px-2 pb-2 pt-0 space-y-1 border-t border-purple-500/10">
              {blocks.map((block) => renderReasoningBlock(block, true))}
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderFileEdit = (edit: FileEdit) => {
    const isExpanded = expandedFiles.has(edit.id);

    const actionLabel = edit.action === 'create' ? 'Created' : edit.action === 'edit' ? 'Modified' : 'Deleted';
    const actionColor =
      edit.action === 'create'
        ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
        : edit.action === 'edit'
        ? 'text-aqua-400 bg-aqua-500/10 border-aqua-500/20'
        : 'text-red-400 bg-red-500/10 border-red-500/20';

    return (
      <div
        key={edit.id}
        className="rounded-xl overflow-hidden bg-gray-800/50 border border-gray-700/30 shadow-sm w-full"
      >
        <div className="flex items-center gap-2 px-3 py-2 hover:bg-gray-750/30 transition-colors">
          <button onClick={() => toggleFile(edit.id)} className="text-gray-600 hover:text-gray-400 flex-shrink-0">
            {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          </button>
          <span
            className={cn(
              'w-5 h-5 flex items-center justify-center rounded-md text-xs flex-shrink-0',
              edit.action === 'create' && 'bg-emerald-500/15 text-emerald-400',
              edit.action === 'edit' && 'bg-aqua-500/15 text-aqua-400',
              edit.action === 'delete' && 'bg-red-500/15 text-red-400'
            )}
          >
            {edit.action === 'create' && <Plus className="w-3 h-3" />}
            {edit.action === 'edit' && <Pencil className="w-3 h-3" />}
            {edit.action === 'delete' && <Trash2 className="w-3 h-3" />}
          </span>
          <span className="flex-1 text-xs text-gray-300 font-mono truncate min-w-0">{edit.filePath}</span>
          <span className={cn('text-[10px] px-1.5 py-0.5 rounded border font-medium whitespace-nowrap flex-shrink-0', actionColor)}>
            {actionLabel}
          </span>
          <button
            onClick={() => onRevertFile(edit.id)}
            className="p-1 text-gray-600 hover:text-amber-400 hover:bg-gray-700/50 rounded-md transition-colors flex-shrink-0"
            title="Revert this file edit"
          >
            <RotateCcw className="w-3 h-3" />
          </button>
        </div>

        {isExpanded && edit.diff && (
          <div className="px-3 pb-3">
            <DiffPreview diff={edit.diff} action={edit.action} />
          </div>
        )}
      </div>
    );
  };

  const pendingApproval = toolCalls.find(
    (tc) => tc.status === 'pending' && tc.approvalRequired === true,
  );

  // Parse command parts for auto-approve feature
  const parseCommandParts = (toolName: string, input: Record<string, unknown>): { label: string; value: string; key: string }[] => {
    const parts: { label: string; value: string; key: string }[] = [];
    
    // Tool name is always first
    parts.push({ label: 'Tool', value: toolName, key: 'tool' });
    
    // Extract path-like arguments
    if (input.path) {
      parts.push({ label: 'Path', value: String(input.path), key: 'path' });
      
      // Extract file extension
      const ext = String(input.path).split('.').pop();
      if (ext) {
        parts.push({ label: 'Extension', value: `.${ext}`, key: 'ext' });
      }
      
      // Extract directory
      const dir = String(input.path).split('/').slice(0, -1).join('/');
      if (dir) {
        parts.push({ label: 'Directory', value: dir, key: 'dir' });
      }
    }
    
    // Extract other notable args
    if (input.packages && Array.isArray(input.packages)) {
      parts.push({ label: 'Packages', value: input.packages.join(', '), key: 'packages' });
    }
    
    if (input.context) {
      parts.push({ label: 'Context', value: String(input.context).slice(0, 30) + '...', key: 'context' });
    }
    
    if (input.replacement) {
      parts.push({ label: 'Replacement', value: String(input.replacement).slice(0, 30) + '...', key: 'replacement' });
    }
    
    return parts.slice(0, 5);
  };

  const [autoApproveRuleKeys, setAutoApproveRuleKeys] = useState<Set<string>>(
    new Set(autoApproveRules.map((rule) => `${rule.field}:${rule.value}`)),
  );

  const mapPartKeyToField = (key: string): AutoApproveRule['field'] => {
    if (key === 'tool') return 'tool';
    if (key === 'path') return 'path';
    if (key === 'ext') return 'extension';
    if (key === 'dir') return 'directory';
    return 'pattern';
  };

  const toggleAutoApprove = (key: string, value: string) => {
    const dbField = mapPartKeyToField(key);
    const token = `${dbField}:${value}`;
    const next = new Set(autoApproveRuleKeys);
    if (next.has(token)) {
      next.delete(token);
    } else {
      next.add(token);
    }
    setAutoApproveRuleKeys(next);
    onUpdateAutoApproveRules?.(
      Array.from(next).map((entry) => {
        const [field, ...rest] = entry.split(':');
        return {
          field: field as AutoApproveRule['field'],
          value: rest.join(':'),
          enabled: true,
        };
      }),
    );
  };

  const commandParts = pendingApproval
    ? parseCommandParts(pendingApproval.name, pendingApproval.input)
    : [];

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-2xl shadow-xl shadow-black/30 border border-gray-700/40 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700/40 bg-gray-850 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-aqua-400" />
          <h2 className="font-semibold text-gray-200 text-sm">Agent Activity</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-600 font-mono">{toolCalls.length} calls</span>
          <span className="text-gray-700">·</span>
          <span className="text-[10px] text-gray-600 font-mono">{fileEdits.length} edits</span>
          <span className="text-gray-700">·</span>
          <span className="text-[10px] text-purple-400/50 font-mono">{reasoningBlocks.length} thoughts</span>
        </div>
      </div>

      {/* Unified Timeline */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {timeline.map(({ checkpoint, items }) => {
          const isCollapsed = collapsedCheckpoints.has(checkpoint.id);

          return (
            <div key={checkpoint.id} className="space-y-2">
              {/* Checkpoint Header */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => toggleCheckpointCollapse(checkpoint.id)}
                  className="flex items-center gap-2 group"
                >
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-gray-800/80 rounded-lg border border-gray-700/40 shadow-sm group-hover:border-gray-600/50 transition-colors">
                    {isCollapsed ? (
                      <ChevronRight className="w-3 h-3 text-gray-500" />
                    ) : (
                      <ChevronDown className="w-3 h-3 text-gray-500" />
                    )}
                    <GitBranch className="w-3 h-3 text-aqua-400" />
                    <span className="text-[11px] text-gray-300 font-medium whitespace-nowrap">{checkpoint.label}</span>
                    <span className="text-[10px] text-gray-600 whitespace-nowrap">
                      {items.length} actions
                    </span>
                  </div>
                </button>
                <button
                  onClick={() => onRevertCheckpoint(checkpoint.id)}
                  className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-amber-400/80 hover:text-amber-300 hover:bg-gray-800 rounded-lg border border-gray-700/30 transition-colors flex-shrink-0"
                  title="Revert all changes from this checkpoint"
                >
                  <RotateCcw className="w-2.5 h-2.5" />
                  <span>Revert</span>
                </button>
              </div>

              {/* Timeline Items */}
              {!isCollapsed && (
                <div className="ml-3 pl-3 border-l border-gray-700/30">
                  {items.map((item, idx) => {
                    const prevItem = idx > 0 ? items[idx - 1] : null;
                    const showConnector = prevItem !== null;

                    // Determine if we need a type-transition connector
                    const isTypeTransition = prevItem !== null && prevItem.type !== item.type;

                    return (
                      <div key={item.type === 'tool' ? item.call.id : item.type === 'file' ? item.edit.id : item.type === 'reasoning' ? item.block.id : item.type === 'reasoning_group' ? `thinking-${item.checkpointId}` : `parallel-${idx}`}>
                        {/* Connector line between items */}
                        {showConnector && (
                          <div className="flex justify-center py-0.5">
                            <div
                              className={cn(
                                'h-4',
                                isTypeTransition
                                  ? 'w-px bg-gradient-to-b from-gray-700/60 via-gray-600/40 to-gray-700/60'
                                  : 'w-px bg-gray-700/30'
                              )}
                            />
                          </div>
                        )}

                        {item.type === 'reasoning' && renderReasoningBlock(item.block)}
                        {item.type === 'reasoning_group' && renderThinkingGroup(item.checkpointId, item.blocks)}

                        {item.type === 'tool' && (
                          <div className="flex justify-center">
                            {renderToolCall(item.call)}
                          </div>
                        )}

                        {item.type === 'parallel' && (() => {
                          const groupKey = `parallel-${checkpoint.id}-${idx}`;
                          const isGroupExpanded = expandedParallelGroups.has(groupKey);

                          return (
                            <div className="flex justify-center">
                              <div className="inline-flex flex-col border border-aqua-500/15 rounded-xl overflow-hidden bg-aqua-500/3">
                                {/* Parallel group header with caret */}
                                <button
                                  onClick={() => toggleParallelGroup(groupKey, item.calls)}
                                  className="flex items-center gap-2 px-2.5 py-1.5 hover:bg-aqua-500/5 transition-colors"
                                >
                                  <span className="text-aqua-400/60 flex-shrink-0">
                                    {isGroupExpanded ? (
                                      <ChevronDown className="w-3 h-3" />
                                    ) : (
                                      <ChevronRight className="w-3 h-3" />
                                    )}
                                  </span>
                                  <GitBranch className="w-3 h-3 text-aqua-400/70" />
                                  <span className="text-[10px] text-aqua-400/70 font-medium whitespace-nowrap">
                                    Parallel · {item.calls.length} calls
                                  </span>
                                  <div className="flex items-center gap-1 ml-1">
                                    {item.calls.map(c => (
                                      <span key={c.id} className="flex-shrink-0">{statusIcons[c.status]}</span>
                                    ))}
                                  </div>
                                </button>

                                {/* Expanded parallel calls */}
                                {isGroupExpanded && (
                                  <div className="px-2 pb-2 space-y-1 border-t border-aqua-500/10">
                                    <div className="h-1" />
                                    {item.calls.map((call) => renderToolCall(call, true))}
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })()}

                        {item.type === 'file' && (
                          <div>
                            {renderFileEdit(item.edit)}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Tool Call Approval Popup */}
      {pendingApproval && (
      <div className="flex-shrink-0 border-t border-gray-700/40 bg-gray-850 p-3">
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 overflow-hidden shadow-lg">
          {/* Header */}
          <div className="flex items-center gap-2 px-3 py-2 bg-amber-500/10 border-b border-amber-500/20">
            <div className="w-5 h-5 rounded-md bg-amber-500/20 flex items-center justify-center">
              <ShieldCheck className="w-3 h-3 text-amber-400" />
            </div>
            <span className="text-xs font-medium text-amber-300">Tool Approval Required</span>
            <Loader2 className="w-3 h-3 text-amber-400/60 animate-spin ml-auto" />
          </div>

          {/* Tool Call Info */}
          <div className="p-3 space-y-3">
            {/* Tool Name and Path */}
            <div className="flex items-center gap-2">
              <span className="text-aqua-400">{toolIcons[pendingApproval.name] || <FileCode className="w-3.5 h-3.5" />}</span>
              <span className="text-xs font-mono text-gray-300">{pendingApproval.name}</span>
              <span className="text-[10px] text-gray-600 font-mono">{String(pendingApproval.input.path ?? '')}</span>
            </div>

            {/* Description */}
            <p className="text-[11px] text-gray-500 leading-relaxed">
              {pendingApproval.description ?? 'Waiting for approval to run this tool call.'}
            </p>

            {/* Command Parts for Auto-Approve */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-1.5">
                <Zap className="w-3 h-3 text-emerald-400/60" />
                <span className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">Auto-approve in future</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {commandParts.map((part) => {
                  const normalized = `${mapPartKeyToField(part.key)}:${part.value}`;
                  const isAutoApproved = autoApproveRuleKeys.has(normalized);
                  return (
                    <button
                      key={part.key}
                      onClick={() => toggleAutoApprove(part.key, part.value)}
                      className={cn(
                        'inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-mono transition-all border',
                        isAutoApproved
                          ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
                          : 'bg-gray-800/50 border-gray-700/40 text-gray-400 hover:border-gray-600/50 hover:text-gray-300'
                      )}
                      title={`${part.label}: ${part.value}`}
                    >
                      <span
                        className={cn(
                          'w-3 h-3 rounded-sm flex items-center justify-center flex-shrink-0 transition-colors',
                          isAutoApproved
                            ? 'bg-emerald-500/30'
                            : 'bg-gray-700/50'
                        )}
                      >
                        {isAutoApproved && <Check className="w-2 h-2 text-emerald-300" />}
                      </span>
                      <span className="text-gray-500">{part.label}:</span>
                      <span className={cn(
                        'max-w-[100px] truncate',
                        isAutoApproved ? 'text-emerald-300' : 'text-gray-300'
                      )}>
                        {part.value}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2 pt-1">
              <button
                onClick={() => onApproveCommand?.(pendingApproval.id)}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/30 text-emerald-300 text-xs font-medium transition-colors"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Approve</span>
              </button>
              <button
                onClick={() => onRejectCommand?.(pendingApproval.id)}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 text-xs font-medium transition-colors"
              >
                <X className="w-3.5 h-3.5" />
                <span>Reject</span>
              </button>
            </div>
          </div>
        </div>
      </div>
      )}
    </div>
  );
}
