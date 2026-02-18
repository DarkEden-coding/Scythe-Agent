import { useState, useEffect, useRef } from 'react';
import { MessageSquare, Clock, Hash, MoreHorizontal, PinIcon, Trash2 } from 'lucide-react';
import type { ProjectChat } from '@/types';
import { cn } from '@/utils/cn';

interface ChatListItemProps {
  readonly chat: ProjectChat;
  readonly isActive: boolean;
  readonly isHovered: boolean;
  readonly isSelected?: boolean;
  readonly editMenuOpen?: boolean;
  readonly onSelect: () => void;
  readonly onMouseEnter: () => void;
  readonly onMouseLeave: () => void;
  readonly onEditMenuClose?: () => void;
  readonly formatRelativeTime: (date: Date) => string;
  readonly onRename?: (chatId: string, title: string) => Promise<void> | void;
  readonly onPin?: (chatId: string, isPinned: boolean) => Promise<void> | void;
  readonly onDelete?: (chatId: string) => Promise<void> | void;
  readonly onRequestDelete?: (chat: ProjectChat) => void;
}

export function ChatListItem({
  chat,
  isActive,
  isHovered,
  isSelected = false,
  editMenuOpen = false,
  onSelect,
  onMouseEnter,
  onMouseLeave,
  onEditMenuClose,
  formatRelativeTime,
  onRename,
  onPin,
  onDelete,
  onRequestDelete,
}: ChatListItemProps) {
  const [showMenu, setShowMenu] = useState(false);
  const [menuPosition, setMenuPosition] = useState<{ x: number; y: number } | null>(null);
  const [menuFocusedIndex, setMenuFocusedIndex] = useState(0);
  const menuContainerRef = useRef<HTMLDivElement>(null);
  const menuButtonRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const menuVisible = showMenu || editMenuOpen;

  const openMenuAtCursor = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const menuWidth = 144;
    const menuHeight = 140;
    const x = Math.min(e.clientX, window.innerWidth - menuWidth - 8);
    const y = Math.min(e.clientY, window.innerHeight - menuHeight - 8);
    setMenuPosition({ x: Math.max(8, x), y: Math.max(8, y) });
    setShowMenu(true);
  };

  const openMenuDefault = () => {
    setMenuPosition(null);
    setShowMenu(true);
    setMenuFocusedIndex(0);
  };

  const closeMenu = () => {
    setShowMenu(false);
    setMenuPosition(null);
    onEditMenuClose?.();
  };

  useEffect(() => {
    if (editMenuOpen) {
      setMenuPosition(null);
      setShowMenu(true);
      setMenuFocusedIndex(0);
    }
  }, [editMenuOpen]);

  useEffect(() => {
    if (!menuVisible) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (menuContainerRef.current && !menuContainerRef.current.contains(e.target as Node)) {
        closeMenu();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [menuVisible]);

  useEffect(() => {
    if (!menuVisible) return;
    const MENU_ITEMS = 3;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMenuFocusedIndex((i) => (i + 1) % MENU_ITEMS);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMenuFocusedIndex((i) => (i - 1 + MENU_ITEMS) % MENU_ITEMS);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        menuButtonRefs.current[menuFocusedIndex]?.click();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        closeMenu();
      }
    };
    globalThis.addEventListener('keydown', handleKeyDown);
    return () => globalThis.removeEventListener('keydown', handleKeyDown);
  }, [menuVisible, menuFocusedIndex]);

  return (
    <div
      ref={menuContainerRef}
      id={`chat-${chat.id}`}
      className="relative"
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onContextMenu={openMenuAtCursor}
    >
      <div
        role="group"
        className={cn(
          'w-full flex items-start gap-2.5 px-3 py-2.5 rounded-lg transition-all text-left group',
          isActive ? 'bg-aqua-500/10 border border-aqua-500/20 shadow-sm' : 'hover:bg-gray-800/50 border border-transparent',
          isSelected && !isActive && 'ring-1 ring-inset ring-gray-600/60',
        )}
      >
        <button
          type="button"
          onClick={onSelect}
          className="flex-1 min-w-0 text-left flex flex-col items-stretch"
        >
          {isActive && (
            <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-aqua-400 rounded-r-full pointer-events-none" />
          )}
          <div className="flex items-center gap-1.5 mb-0.5">
            <MessageSquare className={cn('w-3 h-3 shrink-0', isActive ? 'text-aqua-400' : 'text-gray-500')} />
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
        </button>
        {(isHovered || menuVisible) && (
          <button
            type="button"
            onClick={() => (menuVisible ? closeMenu() : openMenuDefault())}
            className="flex items-center gap-0.5 shrink-0 mt-0.5 p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 rounded-md transition-colors"
          >
            <MoreHorizontal className="w-3 h-3" />
          </button>
        )}
      </div>
      {menuVisible && (
        <div
          className="z-20 w-36 bg-gray-800 border border-gray-700/60 rounded-xl shadow-xl shadow-black/40 py-1 overflow-hidden"
          style={
            menuPosition
              ? { position: 'fixed', left: menuPosition.x, top: menuPosition.y }
              : { position: 'absolute', right: 8, top: '100%', marginTop: 2 }
          }
        >
          <button
            ref={(el) => { menuButtonRefs.current[0] = el; }}
            type="button"
            onClick={() => {
              closeMenu();
              onPin?.(chat.id, !chat.isPinned);
            }}
            className={cn(
              'w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-300 transition-colors',
              menuFocusedIndex === 0 ? 'bg-gray-700/50' : 'hover:bg-gray-700/50',
            )}
          >
            <PinIcon className="w-3 h-3" />
            {chat.isPinned ? 'Unpin chat' : 'Pin chat'}
          </button>
          <button
            ref={(el) => { menuButtonRefs.current[1] = el; }}
            type="button"
            onClick={() => {
              closeMenu();
              const next = globalThis.prompt('Rename chat', chat.title);
              if (next?.trim()) onRename?.(chat.id, next.trim());
            }}
            className={cn(
              'w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-300 transition-colors',
              menuFocusedIndex === 1 ? 'bg-gray-700/50' : 'hover:bg-gray-700/50',
            )}
          >
            <MessageSquare className="w-3 h-3" />
            Rename
          </button>
          <div className="my-1 h-px bg-gray-700/50" />
          <button
            ref={(el) => { menuButtonRefs.current[2] = el; }}
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              closeMenu();
              onRequestDelete?.(chat);
            }}
            className={cn(
              'w-full flex items-center gap-2 px-3 py-1.5 text-xs transition-colors',
              menuFocusedIndex === 2 ? 'bg-red-500/10 text-red-400' : 'text-red-400 hover:bg-red-500/10',
            )}
          >
            <Trash2 className="w-3 h-3" />
            Delete
          </button>
        </div>
      )}
    </div>
  );
}
