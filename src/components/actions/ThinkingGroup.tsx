import { ChevronDown, ChevronRight, Sparkles } from 'lucide-react';
import type { ReasoningBlock } from '@/types';
import { ReasoningBlockView } from './ReasoningBlockView';
import { cn } from '@/utils/cn';

interface ThinkingGroupProps {
  checkpointId: string;
  blocks: ReasoningBlock[];
  isExpanded: boolean;
  expandedBlockIds: Set<string>;
  onToggleGroup: () => void;
  onToggleBlock: (blockId: string) => void;
  formatDuration: (ms: number) => string;
}

export function ThinkingGroup({
  checkpointId,
  blocks,
  isExpanded,
  expandedBlockIds,
  onToggleGroup,
  onToggleBlock,
  formatDuration,
}: ThinkingGroupProps) {
  return (
    <div key={`thinking-${checkpointId}`} className="flex justify-center">
      <div
        className={cn(
          'rounded-lg border transition-all overflow-hidden',
          'border-purple-500/15 bg-purple-500/[0.03] hover:bg-purple-500/[0.06]',
          isExpanded ? 'w-[92%]' : 'inline-flex',
        )}
      >
        <button
          onClick={onToggleGroup}
          className="flex items-center gap-1.5 px-2 py-1.5 w-full min-w-0"
        >
          <span className="text-purple-400/60 flex-shrink-0">
            {isExpanded ? <ChevronDown className="w-2.5 h-2.5" /> : <ChevronRight className="w-2.5 h-2.5" />}
          </span>
          <Sparkles className="w-2.5 h-2.5 text-purple-400/50 flex-shrink-0" />
          <span className="text-[10px] text-purple-300/70 font-medium whitespace-nowrap">
            Thinking · {blocks.length} {blocks.length === 1 ? 'thought' : 'thoughts'}
          </span>
        </button>
        {isExpanded && (
          <div className="px-2 pb-2 pt-0 space-y-1 border-t border-purple-500/10">
            {blocks.map((block) => (
              <ReasoningBlockView
                key={block.id}
                block={block}
                compact
                isExpanded={expandedBlockIds.has(block.id)}
                onToggle={() => onToggleBlock(block.id)}
                formatDuration={formatDuration}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
