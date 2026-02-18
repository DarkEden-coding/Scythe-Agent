import { ChevronDown, ChevronRight, Sparkles } from 'lucide-react';
import type { ReasoningBlock } from '@/types';
import { Markdown } from '@/components/Markdown';
import { cn } from '@/utils/cn';

interface ReasoningBlockViewProps {
  block: ReasoningBlock;
  compact?: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  formatDuration: (ms: number) => string;
}

export function ReasoningBlockView({
  block,
  compact = true,
  isExpanded,
  onToggle,
  formatDuration,
}: ReasoningBlockViewProps) {
  const previewText = block.content.split('\n')[0].slice(0, compact ? 40 : 60).trim() || '…';

  return (
    <div className="flex flex-col">
      <button
        onClick={onToggle}
        className={cn(
          'flex items-center gap-1.5 text-left w-full rounded-md px-2 py-1 transition-colors',
          'hover:bg-purple-500/[0.06] border border-transparent hover:border-purple-500/15',
        )}
      >
        <span className="text-purple-400/60 flex-shrink-0">
          {isExpanded ? <ChevronDown className="w-2.5 h-2.5" /> : <ChevronRight className="w-2.5 h-2.5" />}
        </span>
        <Sparkles className="w-2.5 h-2.5 text-purple-400/50 flex-shrink-0" />
        <span className="text-[10px] text-purple-300/60 font-mono truncate flex-1">{previewText}</span>
        {block.duration && (
          <span className="text-[9px] text-purple-400/30 font-mono whitespace-nowrap">
            {formatDuration(block.duration)}
          </span>
        )}
      </button>
      {isExpanded && (
        <div className="mt-1 ml-5 pl-2 border-l border-purple-500/15 text-[10px] text-purple-200/50 leading-relaxed max-h-[200px] overflow-y-auto">
          <Markdown content={block.content} className="text-[10px] text-purple-200/50" />
        </div>
      )}
    </div>
  );
}
