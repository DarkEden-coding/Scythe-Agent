import { Send, Square } from 'lucide-react';
import { cn } from '@/utils/cn';

interface MessageInputProps {
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly onSubmit: () => void;
  readonly onCancel?: () => void;
  readonly composeMode?: 'default' | 'planning';
  readonly onComposeModeChange?: (mode: 'default' | 'planning') => void;
  readonly activeChatId: string | null;
  readonly disabled?: boolean;
  readonly isProcessing?: boolean;
}

export function MessageInput({
  value,
  onChange,
  onSubmit,
  onCancel,
  composeMode = 'default',
  onComposeModeChange,
  activeChatId,
  disabled = false,
  isProcessing = false,
}: MessageInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (isProcessing) onCancel?.();
      else onSubmit();
    }
  };

  return (
    <div className={cn('space-y-2', !activeChatId && 'opacity-50 pointer-events-none')}>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => onComposeModeChange?.('default')}
          className={cn(
            'px-2 py-1 text-[10px] rounded-md border transition-colors',
            composeMode === 'default'
              ? 'bg-gray-700 border-gray-500 text-gray-100'
              : 'border-gray-700/60 text-gray-400 hover:text-gray-200 hover:bg-gray-800/70',
          )}
        >
          Chat
        </button>
        <button
          type="button"
          onClick={() => onComposeModeChange?.('planning')}
          className={cn(
            'px-2 py-1 text-[10px] rounded-md border transition-colors',
            composeMode === 'planning'
              ? 'bg-cyan-500/20 border-cyan-400/50 text-cyan-200'
              : 'border-gray-700/60 text-gray-400 hover:text-cyan-200 hover:bg-cyan-500/10',
          )}
        >
          Planning
        </button>
      </div>
      <div className="flex items-end gap-2">
        <div className="flex-1 relative">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={
            !activeChatId
              ? 'Select or create a chat to continue'
              : composeMode === 'planning'
                ? 'Describe what to explore, plan, or refine in the active plan...'
                : 'Describe what you want to build...'
          }
          className="w-full px-4 py-3 bg-gray-800 border border-gray-700/50 rounded-xl text-gray-200 placeholder-gray-500 resize-none focus:outline-none focus:border-aqua-500/50 focus:ring-1 focus:ring-aqua-500/30 transition-all text-sm disabled:cursor-not-allowed"
          rows={2}
          disabled={!activeChatId || disabled}
          onKeyDown={handleKeyDown}
        />
        </div>
        {isProcessing ? (
          <button
            onClick={onCancel}
            disabled={!activeChatId}
            className="p-3 bg-amber-500/90 hover:bg-amber-500 text-gray-950 rounded-xl transition-colors shadow-lg shadow-amber-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Stop"
          >
            <Square className="w-4 h-4 fill-current" />
          </button>
        ) : (
          <button
            onClick={onSubmit}
            disabled={!activeChatId || disabled}
            className="p-3 bg-aqua-500 hover:bg-aqua-400 text-gray-950 rounded-xl transition-colors shadow-lg shadow-aqua-500/20 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-aqua-500"
          >
            <Send className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}
