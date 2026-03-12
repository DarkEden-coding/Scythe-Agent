import { useState } from 'react';
import { Brain, ChevronRight, Folder, Plus, Trash2 } from 'lucide-react';
import type { Project, ProjectMemory } from '@/types';
import { ChatListItem } from './ChatListItem';
import { ProjectMemoriesPanel } from './ProjectMemoriesPanel';
import { formatRelativeTime } from '@/utils/formatTime';
import { cn } from '@/utils/cn';
import { useQuery } from '@/contexts/QueryContext';

interface ProjectRowProps {
  readonly project: Project;
  readonly isExpanded: boolean;
  readonly activeChatId: string | null;
  readonly hoveredChatId: string | null;
  readonly selectedChatId: string | null;
  readonly editMenuChatId: string | null;
  readonly projectMemories: ProjectMemory[];
  readonly onToggle: (projectId: string) => void;
  readonly onSelectChat: (chatId: string) => void;
  readonly onMouseEnterChat: (chatId: string) => void;
  readonly onMouseLeaveChat: () => void;
  readonly onEditMenuClose: () => void;
  readonly onCreateChat?: (projectId: string) => void;
  readonly onRenameChat?: (chatId: string, title: string) => Promise<void> | void;
  readonly onPinChat?: (chatId: string, isPinned: boolean) => Promise<void> | void;
  readonly onDeleteChat?: (chatId: string) => Promise<void> | void;
  readonly onRequestDeleteChat?: (chat: import('@/types').ProjectChat) => void;
  readonly onDeleteProject?: (projectId: string) => Promise<void> | void;
  readonly onLoadProjectMemories?: (projectId: string, options?: { force?: boolean }) => Promise<unknown> | void;
  readonly onUpsertProjectMemory?: (projectId: string, payload: { title: string; contentMarkdown: string }) => Promise<{ ok?: boolean; error?: string } | void> | void;
  readonly onDeleteProjectMemory?: (projectId: string, title: string) => Promise<{ ok?: boolean; error?: string } | void> | void;
}

export function ProjectRow({
  project,
  isExpanded,
  activeChatId,
  hoveredChatId,
  selectedChatId,
  editMenuChatId,
  projectMemories,
  onToggle,
  onSelectChat,
  onMouseEnterChat,
  onMouseLeaveChat,
  onEditMenuClose,
  onCreateChat,
  onRenameChat,
  onPinChat,
  onDeleteChat,
  onRequestDeleteChat,
  onDeleteProject,
  onLoadProjectMemories,
  onUpsertProjectMemory,
  onDeleteProjectMemory,
}: ProjectRowProps) {
  const query = useQuery();
  const [showMemories, setShowMemories] = useState(false);

  return (
    <div key={project.id} className="rounded-xl overflow-visible">
      <div
        role="button"
        tabIndex={0}
        onClick={() => onToggle(project.id)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggle(project.id);
          }
        }}
        className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-gray-800/60 rounded-xl transition-colors group cursor-pointer"
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
        <div className="flex items-center gap-1.5 shrink-0">
          {onLoadProjectMemories && onUpsertProjectMemory && onDeleteProjectMemory && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                void onLoadProjectMemories(project.id, { force: true });
                setShowMemories(true);
              }}
              className="inline-flex items-center gap-1 rounded-md border border-aqua-500/20 bg-aqua-500/10 px-2 py-1 text-[10px] text-aqua-300 transition-colors hover:bg-aqua-500/20"
              title="Open project memories"
            >
              <Brain className="h-3 w-3" />
              <span>{projectMemories.length}</span>
            </button>
          )}
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
                if (!(await query.confirm(`Delete project "${project.name}"? This will remove all chats in this project.`, { variant: 'danger', confirmLabel: 'Delete' })))
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
      </div>
      {isExpanded && (
        <div className="ml-4 mr-1 mb-1 space-y-0.5">
          {project.chats.map((chat) => (
            <ChatListItem
              key={chat.id}
              chat={chat}
              isActive={chat.id === activeChatId}
              isHovered={chat.id === hoveredChatId}
              isSelected={chat.id === hoveredChatId || chat.id === selectedChatId}
              editMenuOpen={chat.id === editMenuChatId}
              onSelect={() => onSelectChat(chat.id)}
              onMouseEnter={() => onMouseEnterChat(chat.id)}
              onMouseLeave={onMouseLeaveChat}
              onEditMenuClose={onEditMenuClose}
              formatRelativeTime={formatRelativeTime}
              onRename={onRenameChat}
              onPin={onPinChat}
              onDelete={onDeleteChat}
              onRequestDelete={onRequestDeleteChat}
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
      {onLoadProjectMemories && onUpsertProjectMemory && onDeleteProjectMemory && (
        <ProjectMemoriesPanel
          projectId={project.id}
          projectName={project.name}
          memories={projectMemories}
          visible={showMemories}
          onClose={() => setShowMemories(false)}
          onLoad={onLoadProjectMemories}
          onSave={onUpsertProjectMemory}
          onDelete={onDeleteProjectMemory}
        />
      )}
    </div>
  );
}
