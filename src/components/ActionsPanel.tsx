import { useState, useEffect, useRef } from 'react';
import { Layers, CheckSquare, ChevronDown } from 'lucide-react';
import { SubAgentRun, ToolCall, FileEdit, Checkpoint, ReasoningBlock, TodoItem, ProjectPlan } from '../types';
import { cn } from '@/utils/cn';
import { Timeline } from './actions/Timeline';
import { TodoList } from './actions/TodoList';
import { ApprovalPrompt } from './actions/ApprovalPrompt';
import { PlanCard } from './actions/PlanCard';
import type { AutoApproveRule } from '../api';

interface ActionsPanelProps {
  readonly toolCalls: ToolCall[];
  readonly subAgentRuns?: SubAgentRun[];
  readonly fileEdits: FileEdit[];
  readonly checkpoints: Checkpoint[];
  readonly reasoningBlocks: ReasoningBlock[];
  readonly todos?: TodoItem[];
  readonly plans?: ProjectPlan[];
  readonly streamingReasoningBlockIds?: Set<string>;
  readonly onRevertFile: (fileEditId: string) => void;
  readonly onRevertCheckpoint: (checkpointId: string) => void;
  readonly onApproveCommand?: (toolCallId: string) => void;
  readonly onRejectCommand?: (toolCallId: string) => void;
  readonly onSavePlan?: (
    planId: string,
    content: string,
    baseRevision: number,
  ) => Promise<{ ok: boolean; error?: string; data?: { conflict: boolean; plan: ProjectPlan } }>;
  readonly onApprovePlan?: (
    planId: string,
    action: 'keep_context' | 'clear_context',
  ) => Promise<{ ok: boolean; error?: string; data?: { plan: ProjectPlan; implementationChatId?: string } }>;
  readonly onOpenImplementationChat?: (chatId: string) => void;
  readonly autoApproveRules?: AutoApproveRule[];
  readonly onUpdateAutoApproveRules?: (rules: Omit<AutoApproveRule, 'id' | 'createdAt'>[]) => Promise<void> | void;
}

export function ActionsPanel({
  toolCalls,
  subAgentRuns = [],
  fileEdits,
  checkpoints,
  reasoningBlocks,
  todos = [],
  plans = [],
  streamingReasoningBlockIds = new Set(),
  onRevertFile,
  onRevertCheckpoint,
  onApproveCommand,
  onRejectCommand,
  onSavePlan,
  onApprovePlan,
  onOpenImplementationChat,
  autoApproveRules = [],
  onUpdateAutoApproveRules,
}: ActionsPanelProps) {
  const [expandedTools, setExpandedTools] = useState<Set<string>>(new Set());
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set(fileEdits.map((fe) => fe.id)));
  const [expandedReasoning, setExpandedReasoning] = useState<Set<string>>(new Set());
  const [collapsedCheckpoints, setCollapsedCheckpoints] = useState<Set<string>>(new Set());
  const [expandedParallelGroups, setExpandedParallelGroups] = useState<Set<string>>(new Set());
  const [expandedSubAgents, setExpandedSubAgents] = useState<Set<string>>(new Set());
  const [todoDropdownOpen, setTodoDropdownOpen] = useState(false);
  const todoContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setExpandedReasoning((prev) => {
      const next = new Set(prev);
      reasoningBlocks.forEach((rb) => {
        if (streamingReasoningBlockIds.has(rb.id)) {
          next.add(rb.id);
        } else {
          next.delete(rb.id);
        }
      });
      return next;
    });
  }, [streamingReasoningBlockIds]);

  useEffect(() => {
    if (todos.length === 0) {
      setTodoDropdownOpen(false);
    }
  }, [todos.length]);

  useEffect(() => {
    const handleOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!todoContainerRef.current?.contains(target)) {
        setTodoDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  const toggleTool = (toolId: string) => {
    const next = new Set(expandedTools);
    if (next.has(toolId)) next.delete(toolId);
    else next.add(toolId);
    setExpandedTools(next);
  };
  const toggleFile = (fileId: string) => {
    const next = new Set(expandedFiles);
    if (next.has(fileId)) next.delete(fileId);
    else next.add(fileId);
    setExpandedFiles(next);
  };
  const toggleReasoning = (blockId: string) => {
    const next = new Set(expandedReasoning);
    if (next.has(blockId)) next.delete(blockId);
    else next.add(blockId);
    setExpandedReasoning(next);
  };
  const toggleCheckpointCollapse = (cpId: string) => {
    const next = new Set(collapsedCheckpoints);
    if (next.has(cpId)) next.delete(cpId);
    else next.add(cpId);
    setCollapsedCheckpoints(next);
  };
  const toggleSubAgent = (runId: string) => {
    const next = new Set(expandedSubAgents);
    if (next.has(runId)) next.delete(runId);
    else next.add(runId);
    setExpandedSubAgents(next);
  };
  const toggleParallelGroup = (groupKey: string, _calls: ToolCall[]) => {
    const newExpanded = new Set(expandedParallelGroups);
    if (newExpanded.has(groupKey)) {
      newExpanded.delete(groupKey);
    } else {
      newExpanded.add(groupKey);
    }
    setExpandedParallelGroups(newExpanded);
  };

  const pendingApproval = toolCalls.find(
    (tc) => tc.status === 'pending' && tc.approvalRequired === true,
  );
  const completedTodoCount = todos.filter((t) => t.status === 'completed').length;

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-2xl shadow-xl shadow-black/30 border border-gray-700/40 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700/40 bg-gray-850 shrink-0">
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
          <span className="text-gray-700">·</span>
          <span className="text-[10px] text-cyan-400/60 font-mono">{plans.length} plans</span>
        </div>
      </div>

      <div className="relative flex-1 min-h-0 flex flex-col overflow-hidden">
        {plans.length > 0 && onSavePlan && onApprovePlan && (
          <div className="p-3 pb-0 space-y-2">
            {[...plans]
              .sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
              .map((plan) => (
                <PlanCard
                  key={plan.id}
                  plan={plan}
                  onSave={onSavePlan}
                  onApprove={onApprovePlan}
                  onImplementationChat={onOpenImplementationChat}
                />
              ))}
          </div>
        )}
        <Timeline
          checkpoints={checkpoints}
          toolCalls={toolCalls}
          subAgentRuns={subAgentRuns}
          fileEdits={fileEdits}
          reasoningBlocks={reasoningBlocks}
          streamingReasoningBlockIds={streamingReasoningBlockIds}
          expandedTools={expandedTools}
          expandedFiles={expandedFiles}
          expandedReasoning={expandedReasoning}
          collapsedCheckpoints={collapsedCheckpoints}
          expandedParallelGroups={expandedParallelGroups}
          expandedSubAgents={expandedSubAgents}
          onToggleSubAgent={toggleSubAgent}
          onToggleTool={toggleTool}
          onToggleFile={toggleFile}
          onToggleReasoning={toggleReasoning}
          onToggleCheckpointCollapse={toggleCheckpointCollapse}
          onToggleParallelGroup={toggleParallelGroup}
          onRevertFile={onRevertFile}
          onRevertCheckpoint={onRevertCheckpoint}
        />

        {todos.length > 0 && (
          <section
            aria-label="Task list"
            className="absolute top-0 left-0 pt-3 px-4 z-10 w-fit"
          >
            <div
              ref={todoContainerRef}
              className="relative w-fit"
            >
              <button
                type="button"
                onClick={() => {
                  setTodoDropdownOpen((prev) => !prev);
                }}
                className="flex items-center gap-1.5 px-2 py-1 rounded-full border border-gray-700/50 bg-gray-850/95 hover:bg-gray-800/95 text-[10px] text-gray-300 shadow-md"
              >
                <CheckSquare className="w-3 h-3 text-aqua-400/80" />
                <span>
                  Tasks {completedTodoCount}/{todos.length}
                </span>
                <ChevronDown
                  className={cn(
                    'w-3 h-3 text-gray-500 transition-transform',
                    todoDropdownOpen && 'rotate-180',
                  )}
                />
              </button>
              {todoDropdownOpen && (
                <div className="absolute left-0 top-full mt-2">
                  <TodoList todos={todos} />
                </div>
              )}
            </div>
          </section>
        )}
      </div>

      {pendingApproval && (
        <ApprovalPrompt
          pendingApproval={pendingApproval}
          autoApproveRules={autoApproveRules}
          onApprove={(id) => onApproveCommand?.(id)}
          onReject={(id) => onRejectCommand?.(id)}
          onUpdateAutoApproveRules={onUpdateAutoApproveRules}
        />
      )}
    </div>
  );
}
