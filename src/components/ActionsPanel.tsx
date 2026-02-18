import { useState, useEffect } from 'react';
import { Layers } from 'lucide-react';
import { ToolCall, FileEdit, Checkpoint, ReasoningBlock } from '../types';
import { Timeline } from './actions/Timeline';
import { ApprovalPrompt } from './actions/ApprovalPrompt';
import type { AutoApproveRule } from '../api';

interface ActionsPanelProps {
  readonly toolCalls: ToolCall[];
  readonly fileEdits: FileEdit[];
  readonly checkpoints: Checkpoint[];
  readonly reasoningBlocks: ReasoningBlock[];
  readonly streamingReasoningBlockIds?: Set<string>;
  readonly onRevertFile: (fileEditId: string) => void;
  readonly onRevertCheckpoint: (checkpointId: string) => void;
  readonly onApproveCommand?: (toolCallId: string) => void;
  readonly onRejectCommand?: (toolCallId: string) => void;
  readonly autoApproveRules?: AutoApproveRule[];
  readonly onUpdateAutoApproveRules?: (rules: Omit<AutoApproveRule, 'id' | 'createdAt'>[]) => Promise<void> | void;
}

export function ActionsPanel({
  toolCalls,
  fileEdits,
  checkpoints,
  reasoningBlocks,
  streamingReasoningBlockIds = new Set(),
  onRevertFile,
  onRevertCheckpoint,
  onApproveCommand,
  onRejectCommand,
  autoApproveRules = [],
  onUpdateAutoApproveRules,
}: ActionsPanelProps) {
  const [expandedTools, setExpandedTools] = useState<Set<string>>(new Set());
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set(fileEdits.map((fe) => fe.id)));
  const [expandedReasoning, setExpandedReasoning] = useState<Set<string>>(new Set());
  const [collapsedCheckpoints, setCollapsedCheckpoints] = useState<Set<string>>(new Set());
  const [expandedParallelGroups, setExpandedParallelGroups] = useState<Set<string>>(new Set());

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
  const toggleParallelGroup = (groupKey: string, calls: ToolCall[]) => {
    const newExpanded = new Set(expandedParallelGroups);
    const newExpandedTools = new Set(expandedTools);
    if (newExpanded.has(groupKey)) {
      newExpanded.delete(groupKey);
      calls.forEach((c) => newExpandedTools.delete(c.id));
    } else {
      newExpanded.add(groupKey);
      calls.forEach((c) => newExpandedTools.add(c.id));
    }
    setExpandedParallelGroups(newExpanded);
    setExpandedTools(newExpandedTools);
  };

  const pendingApproval = toolCalls.find(
    (tc) => tc.status === 'pending' && tc.approvalRequired === true,
  );

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
        </div>
      </div>

      <Timeline
        checkpoints={checkpoints}
        toolCalls={toolCalls}
        fileEdits={fileEdits}
        reasoningBlocks={reasoningBlocks}
        streamingReasoningBlockIds={streamingReasoningBlockIds}
        expandedTools={expandedTools}
        expandedFiles={expandedFiles}
        expandedReasoning={expandedReasoning}
        collapsedCheckpoints={collapsedCheckpoints}
        expandedParallelGroups={expandedParallelGroups}
        onToggleTool={toggleTool}
        onToggleFile={toggleFile}
        onToggleReasoning={toggleReasoning}
        onToggleCheckpointCollapse={toggleCheckpointCollapse}
        onToggleParallelGroup={toggleParallelGroup}
        onRevertFile={onRevertFile}
        onRevertCheckpoint={onRevertCheckpoint}
      />

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
