import { Send } from 'lucide-react';
import { cn } from '@/utils/cn';

interface MessageInputProps {
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly onSubmit: () => void;
  readonly activeChatId: string | null;
  readonly disabled?: boolean;
}

export function MessageInput({
  value,
  onChange,
  onSubmit,
  activeChatId,
  disabled = false,
}: MessageInputProps) {
  return (
    <div className={cn('flex items-end gap-2', !activeChatId && 'opacity-50 pointer-events-none')}>
      <div className="flex-1 relative">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={
            activeChatId ? 'Describe what you want to build...' : 'Select or create a chat to continue'
          }
          className="w-full px-4 py-3 bg-gray-800 border border-gray-700/50 rounded-xl text-gray-200 placeholder-gray-500 resize-none focus:outline-none focus:border-aqua-500/50 focus:ring-1 focus:ring-aqua-500/30 transition-all text-sm disabled:cursor-not-allowed"
          rows={2}
          disabled={!activeChatId || disabled}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              onSubmit();
            }
          }}
        />
      </div>
      <button
        onClick={onSubmit}
        disabled={!activeChatId || disabled}
        className="p-3 bg-aqua-500 hover:bg-aqua-400 text-gray-950 rounded-xl transition-colors shadow-lg shadow-aqua-500/20 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-aqua-500"
      >
        <Send className="w-4 h-4" />
      </button>
    </div>
  );
}
