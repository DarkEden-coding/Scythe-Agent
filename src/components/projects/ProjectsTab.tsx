import { useState, useEffect, useCallback, useRef } from 'react';
import { Search, Folder, MessageSquare, GripVertical, Check } from 'lucide-react';
import type { Project } from '@/types';
import { ProjectRow } from './ProjectRow';
import { ReorderPanel } from './ReorderPanel';

interface ProjectsTabProps {
  readonly projects: Project[];
  readonly activeChatId: string | null;
  readonly onSelectChat: (chatId: string) => void;
  readonly onCreateChat?: (projectId: string, title?: string) => Promise<void> | void;
  readonly onRenameChat?: (chatId: string, title: string) => Promise<void> | void;
  readonly onPinChat?: (chatId: string, isPinned: boolean) => Promise<void> | void;
  readonly onDeleteChat?: (chatId: string) => Promise<void> | void;
  readonly onRequestDeleteChat?: (chat: import('@/types').ProjectChat) => void;
  readonly onReorderProjects?: (projectIds: string[]) => Promise<void> | void;
  readonly onReorderChats?: (projectId: string, chatIds: string[]) => Promise<void> | void;
  readonly onDeleteProject?: (projectId: string) => Promise<void> | void;
}

export function ProjectsTab({
  projects,
  activeChatId,
  onSelectChat,
  onCreateChat,
  onRenameChat,
  onPinChat,
  onDeleteChat,
  onRequestDeleteChat,
  onReorderProjects,
  onReorderChats,
  onDeleteProject,
}: ProjectsTabProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set());
  const [hoveredChatId, setHoveredChatId] = useState<string | null>(null);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [editMenuChatId, setEditMenuChatId] = useState<string | null>(null);
  const [reorderMode, setReorderMode] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [reorderExpandedProject, setReorderExpandedProject] = useState<string | null>(null);
  const [dragProjectIndex, setDragProjectIndex] = useState<number | null>(null);
  const [dragOverProjectIndex, setDragOverProjectIndex] = useState<number | null>(null);
  const [dragChatKey, setDragChatKey] = useState<{ projectId: string; chatIndex: number } | null>(null);
  const [dragOverChatIndex, setDragOverChatIndex] = useState<number | null>(null);

  useEffect(() => {
    if (!expandedProjects.size && projects.length) {
      setExpandedProjects(new Set(projects.map((p) => p.id)));
    }
  }, [projects.length, expandedProjects.size]);

  const filteredProjects = searchQuery
    ? projects
        .map((project) => {
          const matchingChats = project.chats.filter(
            (chat) =>
              chat.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
              chat.lastMessage.toLowerCase().includes(searchQuery.toLowerCase()),
          );
          const projectMatches = project.name.toLowerCase().includes(searchQuery.toLowerCase());
          if (projectMatches || matchingChats.length > 0) {
            return { ...project, chats: projectMatches ? project.chats : matchingChats };
          }
          return null;
        })
        .filter(Boolean) as Project[]
    : projects;

  const visibleChats = filteredProjects
    .filter((p) => searchQuery !== '' || expandedProjects.has(p.id))
    .flatMap((p) => p.chats);

  useEffect(() => {
    const chats = filteredProjects
      .filter((p) => searchQuery !== '' || expandedProjects.has(p.id))
      .flatMap((p) => p.chats);
    if (!chats.length) return;
    const inList = (id: string) => chats.some((c) => c.id === id);
    setSelectedChatId((prev) => {
      if (activeChatId != null && inList(activeChatId)) return activeChatId;
      if (prev == null || !inList(prev)) return chats[0].id;
      return prev;
    });
  }, [activeChatId, filteredProjects, expandedProjects, searchQuery]);

  const handleMouseEnterChat = useCallback((chatId: string) => {
    setHoveredChatId(chatId);
  }, []);

  useEffect(() => {
    if (selectedChatId) {
      document.getElementById(`chat-${selectedChatId}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [selectedChatId]);

  useEffect(() => {
    if (reorderMode || editMenuChatId != null) return;
    const projectForChat = (chatId: string) =>
      filteredProjects.find((p) => p.chats.some((c) => c.id === chatId));
    const handleKeyDown = (e: KeyboardEvent) => {
      const input = scrollContainerRef.current?.querySelector('input:focus');
      if (input) return;

      if (document.activeElement?.closest('[role="dialog"]')) return;

      let idx = visibleChats.findIndex((c) => c.id === selectedChatId);
      if (idx < 0 && visibleChats.length) {
        const fallback =
          (activeChatId && visibleChats.find((c) => c.id === activeChatId)) || visibleChats[0];
        setSelectedChatId(fallback.id);
        idx = visibleChats.findIndex((c) => c.id === fallback.id);
        if (idx < 0) return;
      }

      const movePrev = () => {
        e.preventDefault();
        if (idx > 0) setSelectedChatId(visibleChats[idx - 1].id);
      };
      const moveNext = () => {
        e.preventDefault();
        if (idx < visibleChats.length - 1) setSelectedChatId(visibleChats[idx + 1].id);
      };
      const moveFirstInProject = () => {
        e.preventDefault();
        const project = projectForChat(selectedChatId ?? '');
        if (project?.chats.length) setSelectedChatId(project.chats[0].id);
      };
      const moveLastInProject = () => {
        e.preventDefault();
        const lastChat = projectForChat(selectedChatId ?? '')?.chats.at(-1);
        if (lastChat) setSelectedChatId(lastChat.id);
      };

      if (e.key === 'ArrowDown' && !e.shiftKey) moveNext();
      else if (e.key === 'ArrowUp' && !e.shiftKey) movePrev();
      else if (e.key === 'ArrowUp' && e.shiftKey) moveFirstInProject();
      else if (e.key === 'ArrowDown' && e.shiftKey) moveLastInProject();
      else if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (selectedChatId) onSelectChat(selectedChatId);
      } else if (e.key === 'Enter' && e.shiftKey) {
        e.preventDefault();
        if (selectedChatId) setEditMenuChatId(selectedChatId);
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        if (selectedChatId) {
          const chat = visibleChats.find((c) => c.id === selectedChatId);
          if (chat) onRequestDeleteChat?.(chat);
        }
      }
    };
    globalThis.addEventListener('keydown', handleKeyDown);
    return () => globalThis.removeEventListener('keydown', handleKeyDown);
  }, [
    reorderMode,
    editMenuChatId,
    visibleChats,
    selectedChatId,
    activeChatId,
    filteredProjects,
    onSelectChat,
    onRequestDeleteChat,
  ]);

  const toggleProject = (projectId: string) => {
    const next = new Set(expandedProjects);
    if (next.has(projectId)) next.delete(projectId);
    else next.add(projectId);
    setExpandedProjects(next);
  };

  const totalChats = projects.reduce((sum, p) => sum + p.chats.length, 0);

  const moveProject = async (index: number, direction: 'up' | 'down') => {
    const target = direction === 'up' ? index - 1 : index + 1;
    if (target < 0 || target >= projects.length) return;
    const ids = projects.map((p) => p.id);
    [ids[index], ids[target]] = [ids[target], ids[index]];
    await onReorderProjects?.(ids);
  };

  const moveChat = async (projectId: string, chatIndex: number, direction: 'up' | 'down') => {
    const project = projects.find((p) => p.id === projectId);
    if (!project) return;
    const target = direction === 'up' ? chatIndex - 1 : chatIndex + 1;
    if (target < 0 || target >= project.chats.length) return;
    const ids = project.chats.map((c) => c.id);
    [ids[chatIndex], ids[target]] = [ids[target], ids[chatIndex]];
    await onReorderChats?.(projectId, ids);
  };

  const handleProjectDragStart = (e: React.DragEvent, index: number) => {
    setDragProjectIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    if (e.currentTarget instanceof HTMLElement) e.currentTarget.style.opacity = '0.4';
  };

  const handleProjectDragEnd = (e: React.DragEvent) => {
    if (e.currentTarget instanceof HTMLElement) e.currentTarget.style.opacity = '1';
    setDragProjectIndex(null);
    setDragOverProjectIndex(null);
  };

  const handleProjectDrop = async (_e: React.DragEvent, dropIndex: number) => {
    if (dragProjectIndex === null || dragProjectIndex === dropIndex) return;
    const ids = projects.map((p) => p.id);
    const [removed] = ids.splice(dragProjectIndex, 1);
    ids.splice(dropIndex, 0, removed);
    await onReorderProjects?.(ids);
    setDragProjectIndex(null);
    setDragOverProjectIndex(null);
  };

  const handleChatDrop = async (_e: React.DragEvent, projectId: string, dropIndex: number) => {
    const project = projects.find((p) => p.id === projectId);
    if (!project || !dragChatKey?.projectId || dragChatKey.projectId !== projectId || dragChatKey.chatIndex === dropIndex)
      return;
    const ids = project.chats.map((c) => c.id);
    const [removed] = ids.splice(dragChatKey.chatIndex, 1);
    ids.splice(dropIndex, 0, removed);
    await onReorderChats?.(projectId, ids);
    setDragChatKey(null);
    setDragOverChatIndex(null);
  };

  const exitReorderMode = () => {
    setReorderMode(false);
    setReorderExpandedProject(null);
  };

  return (
    <div ref={scrollContainerRef} className="flex-1 overflow-y-auto flex flex-col">
        {!reorderMode && (
          <div className="p-3 border-b border-gray-700/30">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search projects and chats..."
                className="w-full pl-9 pr-3 py-2 bg-gray-800 border border-gray-700/50 rounded-xl text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-aqua-500/40 focus:ring-1 focus:ring-aqua-500/20 transition-all"
              />
            </div>
          </div>
        )}

        {reorderMode && (
          <div className="px-4 py-2.5 border-b border-gray-700/30 bg-gray-800/50 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <GripVertical className="w-3.5 h-3.5 text-aqua-400" />
              <span>Use arrows or drag to reorder</span>
            </div>
            <button
              onClick={exitReorderMode}
              className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium text-aqua-400 bg-aqua-500/10 hover:bg-aqua-500/20 rounded-lg transition-colors"
            >
              <Check className="w-3 h-3" />
              Done
            </button>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {!reorderMode &&
            filteredProjects.map((project) => {
              const isExpanded = searchQuery ? true : expandedProjects.has(project.id);
              return (
                <ProjectRow
                  key={project.id}
                  project={project}
                  isExpanded={isExpanded}
                  activeChatId={activeChatId}
                  hoveredChatId={hoveredChatId}
                  selectedChatId={selectedChatId}
                  editMenuChatId={editMenuChatId}
                  onToggle={toggleProject}
                  onSelectChat={onSelectChat}
                  onMouseEnterChat={handleMouseEnterChat}
                  onMouseLeaveChat={() => setHoveredChatId(null)}
                  onEditMenuClose={() => setEditMenuChatId(null)}
                  onCreateChat={onCreateChat}
                  onRenameChat={onRenameChat}
                  onPinChat={onPinChat}
                  onDeleteChat={onDeleteChat}
                  onRequestDeleteChat={onRequestDeleteChat}
                  onDeleteProject={onDeleteProject}
                />
              );
            })}

          {reorderMode && (
            <ReorderPanel
              projects={projects}
              dragProjectIndex={dragProjectIndex}
              dragOverProjectIndex={dragOverProjectIndex}
              dragChatKey={dragChatKey}
              dragOverChatIndex={dragOverChatIndex}
              reorderExpandedProject={reorderExpandedProject}
              onProjectDragStart={handleProjectDragStart}
              onProjectDragEnd={handleProjectDragEnd}
              onProjectDrop={handleProjectDrop}
              onProjectDragOver={(e, pi) => {
                e.preventDefault();
                if (dragProjectIndex !== null && pi !== dragProjectIndex) setDragOverProjectIndex(pi);
              }}
              onProjectDragLeave={() => setDragOverProjectIndex(null)}
              onChatDragStart={(e, projectId, ci) => {
                e.stopPropagation();
                setDragChatKey({ projectId, chatIndex: ci });
                e.dataTransfer.effectAllowed = 'move';
              }}
              onChatDragEnd={(e) => {
                e.stopPropagation();
                setDragChatKey(null);
                setDragOverChatIndex(null);
              }}
              onChatDragOver={(e, ci) => {
                e.stopPropagation();
                e.preventDefault();
                if (dragChatKey !== null && ci !== dragChatKey.chatIndex) setDragOverChatIndex(ci);
              }}
              onChatDrop={(e, projectId, ci) => {
                e.stopPropagation();
                handleChatDrop(e, projectId, ci);
              }}
              onToggleReorderExpand={(id) =>
                setReorderExpandedProject(reorderExpandedProject === id ? null : id)
              }
              onMoveProject={moveProject}
              onMoveChat={moveChat}
            />
          )}
        </div>

        <div className="p-3 border-t border-gray-700/30 bg-gray-850">
          <div className="flex items-center justify-between text-[11px] text-gray-500">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1">
                <Folder className="w-3 h-3" />
                {projects.length} projects
              </span>
              <span className="flex items-center gap-1">
                <MessageSquare className="w-3 h-3" />
                {totalChats} chats
              </span>
            </div>
            {reorderMode ? (
              <button onClick={exitReorderMode} className="text-aqua-400 hover:text-aqua-300 transition-colors text-[11px]">
                Done
              </button>
            ) : (
              <button
                onClick={() => setReorderMode(true)}
                className="text-gray-500 hover:text-gray-300 transition-colors text-[11px]"
              >
                Re-order
              </button>
            )}
          </div>
        </div>
      </div>
  );
}
