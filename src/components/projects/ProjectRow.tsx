import { ChevronRight, Folder, Plus, Trash2 } from 'lucide-react';
import type { Project } from '@/types';
import { ChatListItem } from './ChatListItem';
import { formatRelativeTime } from '@/utils/formatTime';
import { cn } from '@/utils/cn';

interface ProjectRowProps {
  project: Project;
  isExpanded: boolean;
  activeChatId: string | null;
  hoveredChatId: string | null;
  onToggle: (projectId: string) => void;
  onSelectChat: (chatId: string) => void;
  onMouseEnterChat: (chatId: string) => void;
  onMouseLeaveChat: () => void;
  onCreateChat?: (projectId: string) => void;
  onRenameChat?: (chatId: string, title: string) => Promise<void> | void;
  onPinChat?: (chatId: string, isPinned: boolean) => Promise<void> | void;
  onDeleteChat?: (chatId: string) => Promise<void> | void;
  onDeleteProject?: (projectId: string) => Promise<void> | void;
}

export function ProjectRow({
  project,
  isExpanded,
  activeChatId,
  hoveredChatId,
  onToggle,
  onSelectChat,
  onMouseEnterChat,
  onMouseLeaveChat,
  onCreateChat,
  onRenameChat,
  onPinChat,
  onDeleteChat,
  onDeleteProject,
}: ProjectRowProps) {
  return (
    <div key={project.id} className="rounded-xl overflow-visible">
      <button
        onClick={() => onToggle(project.id)}
        className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-gray-800/60 rounded-xl transition-colors group"
      >
        <ChevronRight
          className={cn('w-3.5 h-3.5 text-gray-500 transition-transform duration-200', isExpanded && 'rotate-90')}
        />
        <div className="flex items-center justify-center w-7 h-7 bg-gray-800 rounded-lg border border-gray-700/50 group-hover:border-gray-600/50 transition-colors shadow-sm">
          <Folder className="w-3.5 h-3.5 text-aqua-400/80" />
        </div>
        <div className="flex-1 text-left min-w-0">
          <div className="text-sm font-medium text-gray-200 truncate">{project.name}</div>
          <div className="text-[10px] text-gray-500 font-mono truncate">{project.path}</div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <span className="text-[10px] text-gray-500 bg-gray-800/80 px-1.5 py-0.5 rounded-md">
            {project.chats.length}
          </span>
          <span className="text-[10px] text-gray-600 hidden group-hover:inline">
            {formatRelativeTime(project.lastAccessed)}
          </span>
          {onDeleteProject && (
            <button
              type="button"
              onClick={async (e) => {
                e.stopPropagation();
                if (!window.confirm(`Delete project "${project.name}"? This will remove all chats in this project.`))
                  return;
                await onDeleteProject(project.id);
              }}
              className="p-1 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-md transition-colors opacity-0 group-hover:opacity-100"
              title="Delete project"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </button>
      {isExpanded && (
        <div className="ml-4 mr-1 mb-1 space-y-0.5">
          {project.chats.map((chat) => (
            <ChatListItem
              key={chat.id}
              chat={chat}
              isActive={chat.id === activeChatId}
              isHovered={chat.id === hoveredChatId}
              onSelect={() => onSelectChat(chat.id)}
              onMouseEnter={() => onMouseEnterChat(chat.id)}
              onMouseLeave={onMouseLeaveChat}
              formatRelativeTime={formatRelativeTime}
              onRename={onRenameChat}
              onPin={onPinChat}
              onDelete={onDeleteChat}
            />
          ))}
          <button
            onClick={() => onCreateChat?.(project.id)}
            className="w-full flex items-center gap-2 px-3 py-2 text-gray-500 hover:text-gray-300 hover:bg-gray-800/40 rounded-lg transition-colors"
          >
            <Plus className="w-3 h-3" />
            <span className="text-xs">New chat</span>
          </button>
        </div>
      )}
    </div>
  );
}
