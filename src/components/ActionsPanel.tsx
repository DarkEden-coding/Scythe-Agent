import { useState } from 'react';
import { Layers } from 'lucide-react';
import { ToolCall, FileEdit, Checkpoint, ReasoningBlock } from '../types';
import { Timeline } from './actions/Timeline';
import { ApprovalPrompt } from './actions/ApprovalPrompt';
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
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set(fileEdits.map((fe) => fe.id)));
  const [expandedReasoning, setExpandedReasoning] = useState<Set<string>>(new Set());
  const [expandedThinkingGroups, setExpandedThinkingGroups] = useState<Set<string>>(new Set());
  const [collapsedCheckpoints, setCollapsedCheckpoints] = useState<Set<string>>(new Set());
  const [expandedParallelGroups, setExpandedParallelGroups] = useState<Set<string>>(new Set());

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
  const toggleThinkingGroup = (checkpointId: string) => {
    const next = new Set(expandedThinkingGroups);
    if (next.has(checkpointId)) next.delete(checkpointId);
    else next.add(checkpointId);
    setExpandedThinkingGroups(next);
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

      <Timeline
        checkpoints={checkpoints}
        toolCalls={toolCalls}
        fileEdits={fileEdits}
        reasoningBlocks={reasoningBlocks}
        expandedTools={expandedTools}
        expandedFiles={expandedFiles}
        expandedReasoning={expandedReasoning}
        expandedThinkingGroups={expandedThinkingGroups}
        collapsedCheckpoints={collapsedCheckpoints}
        expandedParallelGroups={expandedParallelGroups}
        onToggleTool={toggleTool}
        onToggleFile={toggleFile}
        onToggleReasoning={toggleReasoning}
        onToggleThinkingGroup={toggleThinkingGroup}
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
