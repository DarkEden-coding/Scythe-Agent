import { useState, useEffect, useRef } from 'react';
import { MessageSquare, Clock, Hash, MoreHorizontal, PinIcon, Trash2 } from 'lucide-react';
import type { ProjectChat } from '@/types';
import { cn } from '@/utils/cn';

interface ChatListItemProps {
  chat: ProjectChat;
  isActive: boolean;
  isHovered: boolean;
  onSelect: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  formatRelativeTime: (date: Date) => string;
  onRename?: (chatId: string, title: string) => Promise<void> | void;
  onPin?: (chatId: string, isPinned: boolean) => Promise<void> | void;
  onDelete?: (chatId: string) => Promise<void> | void;
}

export function ChatListItem({
  chat,
  isActive,
  isHovered,
  onSelect,
  onMouseEnter,
  onMouseLeave,
  formatRelativeTime,
  onRename,
  onPin,
  onDelete,
}: ChatListItemProps) {
  const [showMenu, setShowMenu] = useState(false);
  const menuContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!showMenu) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (menuContainerRef.current && !menuContainerRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showMenu]);

  return (
    <div ref={menuContainerRef} className="relative" onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave}>
      <div
        role="button"
        tabIndex={0}
        onClick={onSelect}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onSelect();
          }
        }}
        className={cn(
          'w-full flex items-start gap-2.5 px-3 py-2.5 rounded-lg transition-all text-left group',
          isActive ? 'bg-aqua-500/10 border border-aqua-500/20 shadow-sm' : 'hover:bg-gray-800/50 border border-transparent',
        )}
      >
        {isActive && (
          <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-aqua-400 rounded-r-full" />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <MessageSquare className={cn('w-3 h-3 flex-shrink-0', isActive ? 'text-aqua-400' : 'text-gray-500')} />
            <span className={cn('text-xs font-medium truncate', isActive ? 'text-aqua-300' : 'text-gray-300')}>
              {chat.isPinned ? '[Pinned] ' : ''}
              {chat.title}
            </span>
          </div>
          <p className="text-[11px] text-gray-500 truncate pl-[18px]">{chat.lastMessage}</p>
          <div className="flex items-center gap-2 mt-1 pl-[18px]">
            <span className="flex items-center gap-0.5 text-[10px] text-gray-600">
              <Clock className="w-2.5 h-2.5" />
              {formatRelativeTime(chat.timestamp)}
            </span>
            <span className="flex items-center gap-0.5 text-[10px] text-gray-600">
              <Hash className="w-2.5 h-2.5" />
              {chat.messageCount} msgs
            </span>
          </div>
        </div>
        {(isHovered || showMenu) && (
          <div className="flex items-center gap-0.5 flex-shrink-0 mt-0.5">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setShowMenu(!showMenu);
              }}
              className="p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 rounded-md transition-colors"
            >
              <MoreHorizontal className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>
      {showMenu && (
        <div className="absolute right-2 top-full z-20 mt-0.5 w-36 bg-gray-800 border border-gray-700/60 rounded-xl shadow-xl shadow-black/40 py-1 overflow-hidden">
          <button
            type="button"
            onClick={() => onPin?.(chat.id, !chat.isPinned)}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-700/50 transition-colors"
          >
            <PinIcon className="w-3 h-3" />
            {chat.isPinned ? 'Unpin chat' : 'Pin chat'}
          </button>
          <button
            type="button"
            onClick={() => {
              const next = window.prompt('Rename chat', chat.title);
              if (next && next.trim()) onRename?.(chat.id, next.trim());
            }}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-700/50 transition-colors"
          >
            <MessageSquare className="w-3 h-3" />
            Rename
          </button>
          <div className="my-1 h-px bg-gray-700/50" />
          <button
            type="button"
            onClick={async (e) => {
              e.stopPropagation();
              if (!window.confirm('Delete this chat?')) return;
              setShowMenu(false);
              await onDelete?.(chat.id);
            }}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10 transition-colors"
          >
            <Trash2 className="w-3 h-3" />
            Delete
          </button>
        </div>
      )}
    </div>
  );
}
