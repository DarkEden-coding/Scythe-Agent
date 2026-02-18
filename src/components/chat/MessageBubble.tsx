import { User, Bot } from 'lucide-react';
import type { Message } from '@/types';
import { Markdown } from '@/components/Markdown';
import { formatTime } from '@/utils/formatTime';
import { cn } from '@/utils/cn';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  return (
    <div className={cn('flex gap-3', message.role === 'user' ? 'flex-row-reverse' : 'flex-row')}>
      <div
        className={cn(
          'flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center shadow-md',
          message.role === 'user'
            ? 'bg-gradient-to-br from-aqua-400 to-aqua-600'
            : 'bg-gray-750 border border-gray-600/50',
        )}
      >
        {message.role === 'user' ? (
          <User className="w-3.5 h-3.5 text-gray-950" />
        ) : (
          <Bot className="w-3.5 h-3.5 text-aqua-400" />
        )}
      </div>
      <div className={cn('flex-1 max-w-[85%]', message.role === 'user' ? 'text-right' : 'text-left')}>
        <div
          className={cn(
            'inline-block px-4 py-2.5 rounded-2xl text-sm shadow-md',
            message.role === 'user'
              ? 'bg-gradient-to-br from-aqua-500/90 to-aqua-600/90 text-gray-950 rounded-br-md'
              : 'bg-gray-800 text-gray-200 rounded-bl-md border border-gray-700/40',
          )}
        >
          {message.role === 'agent' ? (
            <Markdown content={message.content} />
          ) : (
            <div className="whitespace-pre-wrap">{message.content}</div>
          )}
        </div>
        <div className="mt-1 text-[10px] text-gray-600">{formatTime(message.timestamp)}</div>
      </div>
    </div>
  );
}
