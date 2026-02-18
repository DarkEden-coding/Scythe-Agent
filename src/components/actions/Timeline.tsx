import { ChevronDown, ChevronRight, GitBranch, RotateCcw } from 'lucide-react';
import type { ToolCall, FileEdit, Checkpoint, ReasoningBlock } from '@/types';
import { buildTimeline, type TimelineItem } from './buildTimeline';
import { ToolCallCard, statusIcons } from './ToolCallCard';
import { FileEditCard } from './FileEditCard';
import { ReasoningBlockView } from './ReasoningBlockView';
import { cn } from '@/utils/cn';

function getTimelineItemKey(item: TimelineItem, idx: number): string {
  if (item.type === 'tool') return item.call.id;
  if (item.type === 'file') return item.edit.id;
  if (item.type === 'reasoning') return item.block.id;
  return `parallel-${idx}`;
}

interface ParallelGroupBlockProps {
  readonly groupKey: string;
  readonly calls: ToolCall[];
  readonly isExpanded: boolean;
  readonly onToggle: () => void;
  readonly expandedTools: Set<string>;
  readonly onToggleTool: (id: string) => void;
}

function ParallelGroupBlock({
  groupKey: _groupKey,
  calls,
  isExpanded,
  onToggle,
  expandedTools,
  onToggleTool,
}: ParallelGroupBlockProps) {
  return (
    <div className="flex justify-center">
      <div className="inline-flex flex-col border border-aqua-500/15 rounded-xl overflow-hidden bg-aqua-500/3">
        <button
          type="button"
          onClick={onToggle}
          className="flex items-center gap-2 px-2.5 py-1.5 hover:bg-aqua-500/5 transition-colors"
        >
          <span className="text-aqua-400/60 shrink-0">
            {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          </span>
          <GitBranch className="w-3 h-3 text-aqua-400/70" />
          <span className="text-[10px] text-aqua-400/70 font-medium whitespace-nowrap">
            Parallel · {calls.length} calls
          </span>
          <div className="flex items-center gap-1 ml-1">
            {calls.map((c) => (
              <span key={c.id} className="shrink-0">
                {statusIcons[c.status]}
              </span>
            ))}
          </div>
        </button>
        {isExpanded && (
          <div className="px-2 pb-2 space-y-1 border-t border-aqua-500/10">
            <div className="h-1" />
            {calls.map((call) => (
              <ToolCallCard
                key={call.id}
                call={call}
                isInParallel
                isExpanded={expandedTools.has(call.id)}
                onToggle={() => onToggleTool(call.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface TimelineProps {
  readonly checkpoints: Checkpoint[];
  readonly toolCalls: ToolCall[];
  readonly fileEdits: FileEdit[];
  readonly reasoningBlocks: ReasoningBlock[];
  readonly streamingReasoningBlockIds?: Set<string>;
  readonly expandedTools: Set<string>;
  readonly expandedFiles: Set<string>;
  readonly expandedReasoning: Set<string>;
  readonly collapsedCheckpoints: Set<string>;
  readonly expandedParallelGroups: Set<string>;
  readonly onToggleTool: (id: string) => void;
  readonly onToggleFile: (id: string) => void;
  readonly onToggleReasoning: (id: string) => void;
  readonly onToggleCheckpointCollapse: (id: string) => void;
  readonly onToggleParallelGroup: (groupKey: string, calls: ToolCall[]) => void;
  readonly onRevertFile: (fileEditId: string) => void;
  readonly onRevertCheckpoint: (checkpointId: string) => void;
}

export function Timeline({
  checkpoints,
  toolCalls,
  fileEdits,
  reasoningBlocks,
  streamingReasoningBlockIds = new Set(),
  expandedTools,
  expandedFiles,
  expandedReasoning,
  collapsedCheckpoints,
  expandedParallelGroups,
  onToggleTool,
  onToggleFile,
  onToggleReasoning,
  onToggleCheckpointCollapse,
  onToggleParallelGroup,
  onRevertFile,
  onRevertCheckpoint,
}: TimelineProps) {
  const timeline = buildTimeline(checkpoints, toolCalls, fileEdits, reasoningBlocks);

  return (
    <div className="flex-1 overflow-y-auto p-3 space-y-4">
      {timeline.map(({ checkpoint, items }) => {
        const isCollapsed = collapsedCheckpoints.has(checkpoint.id);

        return (
          <div key={checkpoint.id} className="space-y-2">
            <div className="flex items-center gap-2">
              <button
                onClick={() => onToggleCheckpointCollapse(checkpoint.id)}
                className="flex items-center gap-2 group"
              >
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-gray-800/80 rounded-lg border border-gray-700/40 shadow-sm group-hover:border-gray-600/50 transition-colors">
                  {isCollapsed ? (
                    <ChevronRight className="w-3 h-3 text-gray-500" />
                  ) : (
                    <ChevronDown className="w-3 h-3 text-gray-500" />
                  )}
                  <GitBranch className="w-3 h-3 text-aqua-400" />
                  <span className="text-[11px] text-gray-300 font-medium whitespace-nowrap">
                    {checkpoint.label}
                  </span>
                  <span className="text-[10px] text-gray-600 whitespace-nowrap">
                    {items.length} actions
                  </span>
                </div>
              </button>
              <button
                onClick={() => onRevertCheckpoint(checkpoint.id)}
                className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-amber-400/80 hover:text-amber-300 hover:bg-gray-800 rounded-lg border border-gray-700/30 transition-colors shrink-0"
                title="Revert all changes from this checkpoint"
              >
                <RotateCcw className="w-2.5 h-2.5" />
                <span>Revert</span>
              </button>
            </div>

            {!isCollapsed && (
              <div className="ml-3 pl-3 border-l border-gray-700/30">
                {items.map((item, idx) => {
                  const prevItem = idx > 0 ? items[idx - 1] : null;
                  const showConnector = prevItem !== null;
                  const isTypeTransition = prevItem !== null && prevItem.type !== item.type;

                  const key = getTimelineItemKey(item, idx);

                  return (
                    <div key={key}>
                      {showConnector && (
                        <div className="flex justify-center py-0.5">
                          <div
                            className={cn(
                              'h-4',
                              isTypeTransition
                                ? 'w-px bg-linear-to-b from-gray-700/60 via-gray-600/40 to-gray-700/60'
                                : 'w-px bg-gray-700/30',
                            )}
                          />
                        </div>
                      )}

                      {item.type === 'reasoning' && (
                        <div className="flex justify-center">
                          <ReasoningBlockView
                            block={item.block}
                            isExpanded={expandedReasoning.has(item.block.id)}
                            isStreaming={streamingReasoningBlockIds.has(item.block.id)}
                            onToggle={() => onToggleReasoning(item.block.id)}
                          />
                        </div>
                      )}
                      {item.type === 'tool' && (
                        <div className="flex justify-center">
                          <ToolCallCard
                            call={item.call}
                            isExpanded={expandedTools.has(item.call.id)}
                            onToggle={() => onToggleTool(item.call.id)}
                          />
                        </div>
                      )}
                      {item.type === 'parallel' && (
                        <ParallelGroupBlock
                          groupKey={`parallel-${checkpoint.id}-${idx}`}
                          calls={item.calls}
                          isExpanded={expandedParallelGroups.has(`parallel-${checkpoint.id}-${idx}`)}
                          onToggle={() => onToggleParallelGroup(`parallel-${checkpoint.id}-${idx}`, item.calls)}
                          expandedTools={expandedTools}
                          onToggleTool={onToggleTool}
                        />
                      )}
                      {item.type === 'file' && (
                        <div>
                          <FileEditCard
                            edit={item.edit}
                            isExpanded={expandedFiles.has(item.edit.id)}
                            onToggle={() => onToggleFile(item.edit.id)}
                            onRevert={() => onRevertFile(item.edit.id)}
                          />
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
  );
}
