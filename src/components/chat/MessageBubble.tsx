import { useState, useRef, useEffect } from 'react';
import { User, Bot, Pencil, Check, X } from 'lucide-react';
import type { Message } from '@/types';
import { Markdown } from '@/components/Markdown';
import { formatTime } from '@/utils/formatTime';
import { cn } from '@/utils/cn';

interface MessageBubbleProps {
  readonly message: Message;
  readonly onEdit?: (messageId: string, newContent: string) => void;
  readonly isProcessing?: boolean;
}

export function MessageBubble({ message, onEdit, isProcessing }: MessageBubbleProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(message.content);
  const [isHovered, setIsHovered] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.setSelectionRange(textareaRef.current.value.length, textareaRef.current.value.length);
    }
  }, [isEditing]);

  const handleEditStart = () => {
    setEditValue(message.content);
    setIsEditing(true);
  };

  const handleSave = () => {
    const trimmed = editValue.trim();
    if (!trimmed || trimmed === message.content) {
      setIsEditing(false);
      return;
    }
    onEdit?.(message.id, trimmed);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditValue(message.content);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSave();
    }
    if (e.key === 'Escape') {
      handleCancel();
    }
  };

  return (
    <div
      className={cn('flex gap-3', message.role === 'user' ? 'flex-row-reverse' : 'flex-row')}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div
        className={cn(
          'shrink-0 w-7 h-7 rounded-lg flex items-center justify-center shadow-md',
          message.role === 'user'
            ? 'bg-linear-to-br from-aqua-400 to-aqua-600'
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
        {isEditing ? (
          <div className="flex flex-col gap-1.5">
            <textarea
              ref={textareaRef}
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={Math.max(3, editValue.split('\n').length)}
              className="w-full px-3 py-2 bg-gray-800 border border-aqua-500/50 rounded-xl text-sm text-gray-200 resize-none focus:outline-none focus:ring-1 focus:ring-aqua-500/50"
            />
            <div className="flex items-center justify-end gap-1.5">
              <span className="text-[10px] text-gray-600">⌘↵ to save · Esc to cancel</span>
              <button
                onClick={handleCancel}
                className="flex items-center gap-1 px-2 py-1 text-[11px] text-gray-400 hover:text-gray-200 hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X className="w-3 h-3" />
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={!editValue.trim()}
                className="flex items-center gap-1 px-2 py-1 text-[11px] text-aqua-400 hover:text-aqua-300 hover:bg-aqua-500/10 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Check className="w-3 h-3" />
                Save
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="relative group/bubble">
              <div
                className={cn(
                  'inline-block px-4 py-2.5 rounded-2xl text-sm shadow-md',
                  message.role === 'user'
                    ? 'bg-linear-to-br from-aqua-500/90 to-aqua-600/90 text-gray-950 rounded-br-md'
                    : 'bg-gray-800 text-gray-200 rounded-bl-md border border-gray-700/40',
                )}
              >
                {message.role === 'agent' ? (
                  <Markdown content={message.content} />
                ) : (
                  <div className="whitespace-pre-wrap">{message.content}</div>
                )}
              </div>
              {message.role === 'user' && onEdit && isHovered && !isProcessing && (
                <button
                  onClick={handleEditStart}
                  title="Edit message"
                  className="absolute -left-7 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center text-gray-600 hover:text-aqua-400 hover:bg-gray-800 rounded-md transition-colors"
                >
                  <Pencil className="w-3 h-3" />
                </button>
              )}
            </div>
            <div className="mt-1 text-[10px] text-gray-600">{formatTime(message.timestamp)}</div>
          </>
        )}
      </div>
    </div>
  );
}
