import { useRef, useState, useEffect, useCallback } from 'react';
import { GripVertical, Check, Loader2 } from 'lucide-react';
import type { ProjectChat } from '@/types';

interface ChatTabBarProps {
  readonly chats: ProjectChat[];
  readonly activeChatId: string | null;
  readonly processingChats: Set<string>;
  readonly onSwitchChat: (chatId: string) => void;
  readonly onReorderChats: (projectId: string, chatIds: string[]) => Promise<void> | void;
  readonly projectId: string;
  readonly projectsLoading?: boolean;
  readonly chatLoading?: boolean;
}

export function ChatTabBar({
  chats,
  activeChatId,
  processingChats,
  onSwitchChat,
  onReorderChats,
  projectId,
  projectsLoading = false,
  chatLoading = false,
}: ChatTabBarProps) {
  const headerChatsRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const [dragHeaderChatIndex, setDragHeaderChatIndex] = useState<number | null>(null);
  const [dragOverHeaderChatIndex, setDragOverHeaderChatIndex] = useState<number | null>(null);

  const updateScrollState = useCallback(() => {
    const el = headerChatsRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 0);
    setCanScrollRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 1);
  }, []);

  useEffect(() => {
    updateScrollState();
    const el = headerChatsRef.current;
    if (!el) return;
    const ro = new ResizeObserver(updateScrollState);
    ro.observe(el);
    el.addEventListener('scroll', updateScrollState);
    return () => {
      ro.disconnect();
      el.removeEventListener('scroll', updateScrollState);
    };
  }, [updateScrollState, chats.length]);

  useEffect(() => {
    const el = headerChatsRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => {
      if (e.deltaY === 0) return;
      e.preventDefault();
      el.scrollLeft += e.deltaY;
    };
    el.addEventListener('wheel', handler, { passive: false });
    return () => el.removeEventListener('wheel', handler);
  }, [chats.length, chatLoading, projectsLoading]);

  const handleHeaderChatDrop = useCallback(
    (dropIndex: number) => {
      if (dragHeaderChatIndex === null || dragHeaderChatIndex === dropIndex) return;
      const ids = chats.map((c) => c.id);
      const [removed] = ids.splice(dragHeaderChatIndex, 1);
      ids.splice(dropIndex, 0, removed);
      onReorderChats(projectId, ids);
      setDragHeaderChatIndex(null);
      setDragOverHeaderChatIndex(null);
    },
    [chats, dragHeaderChatIndex, onReorderChats, projectId],
  );

  return (
    <div className="flex items-center gap-0 min-w-0 flex-1 rounded-lg border border-gray-700/50 bg-gray-800/40 px-2 py-1.5">
      {canScrollLeft && chats.length > 0 && (
        <span className="shrink-0 text-gray-500 text-xs">…</span>
      )}
      <div
        ref={headerChatsRef}
        className={`flex items-center gap-2 overflow-x-auto overflow-y-hidden ${canScrollLeft || canScrollRight ? 'pb-1.5' : ''}`}
      >
        {chats.map((c, ci) => {
          const processing = processingChats.has(c.id);
          const isDragging = dragHeaderChatIndex === ci;
          const isDropTarget = dragOverHeaderChatIndex === ci && dragHeaderChatIndex !== ci;
          return (
            <button
              type="button"
              key={c.id}
              draggable
              onDragStart={(e) => {
                setDragHeaderChatIndex(ci);
                e.dataTransfer.effectAllowed = 'move';
              }}
              onDragEnd={() => {
                setDragHeaderChatIndex(null);
                setDragOverHeaderChatIndex(null);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                if (dragHeaderChatIndex !== null && ci !== dragHeaderChatIndex)
                  setDragOverHeaderChatIndex(ci);
              }}
              onDrop={(e) => {
                e.preventDefault();
                handleHeaderChatDrop(ci);
              }}
              onClick={() => onSwitchChat(c.id)}
              className={`flex items-center gap-1.5 shrink-0 px-2 py-1 rounded text-xs transition-colors whitespace-nowrap cursor-grab active:cursor-grabbing ${
                c.id === activeChatId
                  ? 'bg-aqua-500/30 text-aqua-200 border border-aqua-400/40'
                  : 'bg-gray-800/50 text-gray-400 border border-gray-700/40 hover:bg-gray-750 hover:text-gray-300'
              } ${isDragging ? 'opacity-40' : ''} ${isDropTarget ? 'ring-1 ring-aqua-400/60' : ''}`}
              title={c.title}
            >
              <GripVertical className="w-3 h-3 shrink-0 text-gray-500 opacity-60" />
              {processing ? (
                <Loader2 className="w-3 h-3 shrink-0 animate-spin text-aqua-400" />
              ) : (
                <Check className="w-3 h-3 shrink-0 text-green-500/80" />
              )}
              <span className="truncate max-w-[120px]">
                {c.isPinned ? '[Pinned] ' : ''}
                {c.title || 'Untitled'}
              </span>
            </button>
          );
        })}
      </div>
      {canScrollRight && chats.length > 0 && (
        <span className="shrink-0 text-gray-500 text-xs">…</span>
      )}
    </div>
  );
}
