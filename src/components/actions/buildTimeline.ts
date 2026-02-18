/**
 * Pure function to build a unified timeline from checkpoints, tool calls, file edits,
 * and reasoning blocks.
 */

import { uniqueById } from '@/api/normalizers';
import type { ToolCall, FileEdit, Checkpoint, ReasoningBlock } from '@/types';

export type TimelineItem =
  | { type: 'tool'; call: ToolCall }
  | { type: 'parallel'; calls: ToolCall[] }
  | { type: 'file'; edit: FileEdit }
  | { type: 'reasoning'; block: ReasoningBlock };

const TYPE_ORDER: Record<TimelineItem['type'], number> = {
  reasoning: 0,
  tool: 1,
  parallel: 2,
  file: 3,
};

export interface TimelineSegment {
  checkpoint: Checkpoint;
  items: TimelineItem[];
}

export function buildTimeline(
  checkpoints: Checkpoint[],
  toolCalls: ToolCall[],
  fileEdits: FileEdit[],
  reasoningBlocks: ReasoningBlock[],
): TimelineSegment[] {
  const dedupedFileEdits = uniqueById(fileEdits);
  return checkpoints.map((checkpoint) => {
    const cpToolCalls = toolCalls
      .filter((tc) => checkpoint.toolCalls.includes(tc.id))
      .filter(
        (tc) => !(tc.name === 'edit_file' && tc.status === 'completed'),
      );
    const cpFileEdits = dedupedFileEdits.filter((fe) => fe.checkpointId === checkpoint.id);
    const cpReasoningBlocks = reasoningBlocks.filter((rb) =>
      checkpoint.reasoningBlocks?.includes(rb.id),
    );

    const allItems: { timestamp: number; item: TimelineItem }[] = [];

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

    cpReasoningBlocks.forEach((rb) => {
      allItems.push({
        timestamp: rb.timestamp.getTime(),
        item: { type: 'reasoning', block: rb },
      });
    });

    allItems.sort((a, b) => {
      const tsA = Number.isFinite(a.timestamp) ? a.timestamp : 0;
      const tsB = Number.isFinite(b.timestamp) ? b.timestamp : 0;
      if (tsA !== tsB) return tsA - tsB;
      return TYPE_ORDER[a.item.type] - TYPE_ORDER[b.item.type];
    });

    return { checkpoint, items: allItems.map((a) => a.item) };
  });
}
