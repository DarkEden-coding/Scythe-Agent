import { useEffect, useRef } from 'react';
import { ChevronDown, ChevronRight, Sparkles } from 'lucide-react';
import type { ReasoningBlock } from '@/types';
import { Markdown } from '@/components/Markdown';
import { cn } from '@/utils/cn';

interface ReasoningBlockViewProps {
  readonly block: ReasoningBlock;
  readonly compact?: boolean;
  readonly isExpanded: boolean;
  readonly isStreaming?: boolean;
  readonly onToggle: () => void;
}

export function ReasoningBlockView({
  block,
  compact = true,
  isExpanded,
  isStreaming = false,
  onToggle,
}: ReasoningBlockViewProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const previewText = block.content.split('\n')[0].slice(0, compact ? 40 : 60).trim() || '…';

  useEffect(() => {
    if (isStreaming && isExpanded && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [block.content, isStreaming, isExpanded]);

  return (
    <div
      className={cn(
        'flex flex-col transition-all duration-200 ease-out',
        isExpanded ? 'w-full items-start' : 'w-auto items-center',
      )}
    >
      <button
        onClick={onToggle}
        className={cn(
          'flex items-center gap-1.5 text-left rounded-md px-2 py-1 transition-colors',
          'hover:bg-purple-500/6 border border-transparent hover:border-purple-500/15',
          'w-auto shrink-0',
        )}
      >
        <span className="text-purple-400/60 shrink-0">
          {isExpanded ? <ChevronDown className="w-2.5 h-2.5" /> : <ChevronRight className="w-2.5 h-2.5" />}
        </span>
        <Sparkles className="w-2.5 h-2.5 text-purple-400/50 shrink-0" />
        <span className="text-[10px] text-purple-300/60 font-mono truncate flex-1">{previewText}</span>
        {block.duration != null && block.duration > 0 && (
          <span className="text-[9px] text-purple-400/30 font-mono whitespace-nowrap">
            ms: {block.duration}
          </span>
        )}
      </button>
      <div
        className={cn(
          'grid transition-[grid-template-rows] duration-200 ease-out',
          isExpanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
        )}
      >
        <div className="overflow-hidden min-h-0">
          <div
            ref={scrollRef}
            className={cn(
              'mt-1 ml-5 pl-2 border-l border-purple-500/15 text-[10px] text-purple-200/50 leading-relaxed max-h-[200px] overflow-y-auto',
              isExpanded && 'animate-expand-content',
            )}
          >
            <Markdown content={block.content} className="text-[10px] text-purple-200/50" />
          </div>
        </div>
      </div>
    </div>
  );
}
