import { useState, useRef, useEffect } from 'react';
import {
  Send,
  RotateCcw,
  User,
  Bot,
  MessageSquare,
  FolderOpen,
  ChevronRight,
  Search,
  Clock,
  Hash,
  Folder,
  Plus,
  MoreHorizontal,
  Trash2,
  PinIcon,
  X,
  ChevronUp,
  ChevronDown,
  GripVertical,
  ArrowLeft,
  FolderPlus,
  MessageSquarePlus,
  Check,
} from 'lucide-react';
import { Message, Checkpoint, ContextItem, Project, ProjectChat } from '../types';
import { ContextDropdown } from './ContextDropdown';
import { cn } from '../utils/cn';
import { useFilesystemBrowser } from '../api';

interface ChatPanelProps {
  messages: Message[];
  checkpoints: Checkpoint[];
  onRevert: (checkpointId: string) => void;
  contextItems: ContextItem[];
  maxTokens: number;
  onSummarize: () => void;
  onRemoveContextItem: (itemId: string) => void;
  onSendMessage?: (content: string) => void;
  projects: Project[];
  activeChatId?: string;
  onSwitchChat?: (chatId: string) => void;
  isProcessing?: boolean;
  onCreateProject?: (name: string, path: string) => Promise<void> | void;
  onCreateChat?: (projectId: string, title: string) => Promise<void> | void;
  onRenameChat?: (chatId: string, title: string) => Promise<void> | void;
  onPinChat?: (chatId: string, isPinned: boolean) => Promise<void> | void;
  onDeleteChat?: (chatId: string) => Promise<void> | void;
  onReorderProjects?: (projectIds: string[]) => Promise<void> | void;
  onReorderChats?: (projectId: string, chatIds: string[]) => Promise<void> | void;
}

export function ChatPanel({
  messages,
  checkpoints,
  onRevert,
  contextItems,
  maxTokens,
  onSummarize,
  onRemoveContextItem,
  onSendMessage,
  projects,
  activeChatId: externalActiveChatId,
  onSwitchChat,
  isProcessing = false,
  onCreateProject,
  onCreateChat,
  onRenameChat,
  onPinChat,
  onDeleteChat,
  onReorderProjects,
  onReorderChats,
}: ChatPanelProps) {
  const [inputValue, setInputValue] = useState('');
  const [activeTab, setActiveTab] = useState<'chat' | 'projects'>('chat');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeChatId, setActiveChatId] = useState(externalActiveChatId ?? 'chat-1');
  const [hoveredChatId, setHoveredChatId] = useState<string | null>(null);
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set());

  const [showNewModal, setShowNewModal] = useState(false);
  const [newModalStep, setNewModalStep] = useState<'choose' | 'project' | 'chat'>('choose');
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectPath, setNewProjectPath] = useState('');
  const [newChatTitle, setNewChatTitle] = useState('');
  const [newChatProjectId, setNewChatProjectId] = useState('');

  const [reorderMode, setReorderMode] = useState(false);
  const [reorderExpandedProject, setReorderExpandedProject] = useState<string | null>(null);
  const [dragProjectIndex, setDragProjectIndex] = useState<number | null>(null);
  const [dragOverProjectIndex, setDragOverProjectIndex] = useState<number | null>(null);
  const [dragChatKey, setDragChatKey] = useState<{ projectId: string; chatIndex: number } | null>(null);
  const [dragOverChatIndex, setDragOverChatIndex] = useState<number | null>(null);

  const modalRef = useRef<HTMLDivElement>(null);

  const fs = useFilesystemBrowser();

  useEffect(() => {
    setActiveChatId(externalActiveChatId ?? 'chat-1');
  }, [externalActiveChatId]);

  useEffect(() => {
    if (!expandedProjects.size && projects.length) {
      setExpandedProjects(new Set(projects.map((p) => p.id)));
    }
  }, [projects, expandedProjects.size]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        closeNewModal();
      }
    };
    if (showNewModal) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showNewModal]);

  const closeNewModal = () => {
    setShowNewModal(false);
    setNewModalStep('choose');
    setNewProjectName('');
    setNewProjectPath('');
    setNewChatTitle('');
    setNewChatProjectId('');
  };

  const openNewModal = async () => {
    setShowNewModal(true);
    setNewModalStep('choose');
    await fs.load();
  };

  const getCheckpointForMessage = (messageId: string) => checkpoints.find((cp) => cp.messageId === messageId);

  const formatTime = (date: Date) => date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

  const formatRelativeTime = (date: Date) => {
    const now = Date.now();
    const diff = now - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    const weeks = Math.floor(diff / 604800000);

    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    if (weeks < 4) return `${weeks}w ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const toggleProject = (projectId: string) => {
    const next = new Set(expandedProjects);
    if (next.has(projectId)) next.delete(projectId);
    else next.add(projectId);
    setExpandedProjects(next);
  };

  const handleSelectChat = (chatId: string) => {
    setActiveChatId(chatId);
    if (onSwitchChat) onSwitchChat(chatId);
    setActiveTab('chat');
  };

  const handleSend = () => {
    if (!inputValue.trim()) return;
    if (onSendMessage) onSendMessage(inputValue.trim());
    setInputValue('');
  };

  const handleCreateProject = async () => {
    if (!newProjectName.trim() || !newProjectPath) return;
    await onCreateProject?.(newProjectName.trim(), newProjectPath);
    closeNewModal();
  };

  const handleCreateChat = async () => {
    if (!newChatTitle.trim() || !newChatProjectId) return;
    await onCreateChat?.(newChatProjectId, newChatTitle.trim());
    closeNewModal();
  };

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
    if (!project || !dragChatKey || dragChatKey.projectId !== projectId || dragChatKey.chatIndex === dropIndex) return;
    const ids = project.chats.map((c) => c.id);
    const [removed] = ids.splice(dragChatKey.chatIndex, 1);
    ids.splice(dropIndex, 0, removed);
    await onReorderChats?.(projectId, ids);
    setDragChatKey(null);
    setDragOverChatIndex(null);
  };

  const filteredProjects = searchQuery
    ? projects
        .map((project) => {
          const matchingChats = project.chats.filter(
            (chat) =>
              chat.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
              chat.lastMessage.toLowerCase().includes(searchQuery.toLowerCase())
          );
          const projectMatches = project.name.toLowerCase().includes(searchQuery.toLowerCase());
          if (projectMatches || matchingChats.length > 0) {
            return {
              ...project,
              chats: projectMatches ? project.chats : matchingChats,
            };
          }
          return null;
        })
        .filter(Boolean) as Project[]
    : projects;

  const totalChats = projects.reduce((sum, p) => sum + p.chats.length, 0);
  const currentFolders = (fs.data?.children ?? []).filter((item) => item.kind === 'directory');

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-2xl shadow-xl shadow-black/30 border border-gray-700/40 overflow-hidden relative">
      <div className="border-b border-gray-700/40 bg-gray-850">
        <div className="flex items-center justify-between px-4 py-2">
          <div className="flex items-center gap-1">
            <button
              onClick={() => setActiveTab('chat')}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                activeTab === 'chat'
                  ? 'bg-gray-750 text-aqua-400 shadow-sm'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800/50'
              )}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Chat
            </button>
            <button
              onClick={() => setActiveTab('projects')}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                activeTab === 'projects'
                  ? 'bg-gray-750 text-aqua-400 shadow-sm'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800/50'
              )}
            >
              <FolderOpen className="w-3.5 h-3.5" />
              Projects
              <span
                className={cn(
                  'text-[10px] px-1.5 py-0.5 rounded-full',
                  activeTab === 'projects' ? 'bg-aqua-500/20 text-aqua-400' : 'bg-gray-700/50 text-gray-500'
                )}
              >
                {totalChats}
              </span>
            </button>
          </div>

          {activeTab === 'chat' && (
            <ContextDropdown
              contextItems={contextItems}
              maxTokens={maxTokens}
              onSummarize={onSummarize}
              onRemoveItem={onRemoveContextItem}
            />
          )}

          {activeTab === 'projects' && (
            <button
              onClick={openNewModal}
              className="flex items-center gap-1 px-2 py-1 text-[11px] text-aqua-400 hover:bg-gray-750 rounded-lg transition-colors"
            >
              <Plus className="w-3 h-3" />
              New
            </button>
          )}
        </div>
      </div>

      {activeTab === 'chat' && (
        <>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((message) => {
              const checkpoint = message.checkpointId ? getCheckpointForMessage(message.id) : null;

              return (
                <div key={message.id} className="space-y-2">
                  {checkpoint && (
                    <div className="flex items-center gap-2 py-2">
                      <div className="flex-1 h-px bg-gray-700/50" />
                      <div className="flex items-center gap-2 px-2.5 py-1 bg-gray-800 rounded-full border border-gray-700/50 shadow-sm">
                        <div className="w-1.5 h-1.5 rounded-full bg-aqua-400/60" />
                        <span className="text-[11px] text-gray-400">{checkpoint.label}</span>
                        <button
                          onClick={() => onRevert(checkpoint.id)}
                          className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] text-amber-400 hover:text-amber-300 hover:bg-gray-700 rounded transition-colors"
                          title="Revert to this checkpoint"
                        >
                          <RotateCcw className="w-2.5 h-2.5" />
                        </button>
                      </div>
                      <div className="flex-1 h-px bg-gray-700/50" />
                    </div>
                  )}

                  <div className={cn('flex gap-3', message.role === 'user' ? 'flex-row-reverse' : 'flex-row')}>
                    <div
                      className={cn(
                        'flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center shadow-md',
                        message.role === 'user'
                          ? 'bg-gradient-to-br from-aqua-400 to-aqua-600'
                          : 'bg-gray-750 border border-gray-600/50'
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
                            : 'bg-gray-800 text-gray-200 rounded-bl-md border border-gray-700/40'
                        )}
                      >
                        <div className="whitespace-pre-wrap">{message.content}</div>
                      </div>
                      <div className="mt-1 text-[10px] text-gray-600">{formatTime(message.timestamp)}</div>
                    </div>
                  </div>
                </div>
              );
            })}

            {isProcessing && (
              <div className="flex gap-3 pt-2">
                <div className="flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center bg-gray-750 border border-gray-600/50 shadow-md">
                  <Bot className="w-3.5 h-3.5 text-aqua-400" />
                </div>
                <div className="flex items-center gap-2.5 px-4 py-2.5 bg-gray-800 rounded-2xl rounded-bl-md border border-gray-700/40 shadow-md">
                  <div className="w-4 h-4 rounded-full border-2 border-gray-600 border-t-gray-300 animate-spin" />
                  <span className="text-xs text-gray-400">Agent is thinking</span>
                </div>
              </div>
            )}
          </div>

          <div className="p-3 border-t border-gray-700/40 bg-gray-850">
            <div className="flex items-end gap-2">
              <div className="flex-1 relative">
                <textarea
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder="Describe what you want to build..."
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-700/50 rounded-xl text-gray-200 placeholder-gray-500 resize-none focus:outline-none focus:border-aqua-500/50 focus:ring-1 focus:ring-aqua-500/30 transition-all text-sm"
                  rows={2}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                />
              </div>
              <button
                onClick={handleSend}
                className="p-3 bg-aqua-500 hover:bg-aqua-400 text-gray-950 rounded-xl transition-colors shadow-lg shadow-aqua-500/20"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </>
      )}

      {activeTab === 'projects' && (
        <div className="flex-1 overflow-y-auto flex flex-col">
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
                onClick={() => {
                  setReorderMode(false);
                  setReorderExpandedProject(null);
                }}
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
                  <div key={project.id} className="rounded-xl overflow-hidden">
                    <button
                      onClick={() => toggleProject(project.id)}
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
                        <span className="text-[10px] text-gray-500 bg-gray-800/80 px-1.5 py-0.5 rounded-md">{project.chats.length}</span>
                        <span className="text-[10px] text-gray-600 hidden group-hover:inline">{formatRelativeTime(project.lastAccessed)}</span>
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
                            onSelect={() => handleSelectChat(chat.id)}
                            onMouseEnter={() => setHoveredChatId(chat.id)}
                            onMouseLeave={() => setHoveredChatId(null)}
                            formatRelativeTime={formatRelativeTime}
                            onRename={onRenameChat}
                            onPin={onPinChat}
                            onDelete={onDeleteChat}
                          />
                        ))}
                        <button
                          onClick={() => {
                            setNewChatProjectId(project.id);
                            setNewModalStep('chat');
                            setShowNewModal(true);
                          }}
                          className="w-full flex items-center gap-2 px-3 py-2 text-gray-500 hover:text-gray-300 hover:bg-gray-800/40 rounded-lg transition-colors"
                        >
                          <Plus className="w-3 h-3" />
                          <span className="text-xs">New chat</span>
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}

            {reorderMode &&
              projects.map((project, pi) => (
                <div
                  key={project.id}
                  draggable
                  onDragStart={(e) => handleProjectDragStart(e, pi)}
                  onDragEnd={handleProjectDragEnd}
                  onDragOver={(e) => {
                    e.preventDefault();
                    if (dragProjectIndex !== null && pi !== dragProjectIndex) setDragOverProjectIndex(pi);
                  }}
                  onDrop={(e) => handleProjectDrop(e, pi)}
                  onDragLeave={() => setDragOverProjectIndex(null)}
                  className={cn(
                    'rounded-xl border mb-1.5 overflow-hidden transition-all duration-150',
                    dragOverProjectIndex === pi
                      ? 'border-aqua-400/60 bg-aqua-500/5 shadow-md shadow-aqua-500/10'
                      : 'border-gray-700/40 bg-gray-800/30',
                    dragProjectIndex === pi && 'opacity-40'
                  )}
                >
                  <div className="flex items-center gap-2 px-3 py-2.5 group">
                    <div className="cursor-grab active:cursor-grabbing p-0.5 rounded hover:bg-gray-700/50 transition-colors">
                      <GripVertical className="w-3.5 h-3.5 text-gray-500 hover:text-aqua-400 transition-colors" />
                    </div>
                    <div className="flex items-center justify-center w-6 h-6 bg-gray-800 rounded-md border border-gray-700/50">
                      <Folder className="w-3 h-3 text-aqua-400/80" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-medium text-gray-200 truncate block">{project.name}</span>
                      <span className="text-[10px] text-gray-500 font-mono truncate block">{project.path}</span>
                    </div>

                    <div className="flex items-center gap-0.5 flex-shrink-0">
                      {project.chats.length > 0 && (
                        <button
                          onClick={() => setReorderExpandedProject(reorderExpandedProject === project.id ? null : project.id)}
                          className={cn(
                            'p-1 rounded-md text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 transition-colors',
                            reorderExpandedProject === project.id && 'text-aqua-400'
                          )}
                        >
                          <ChevronRight className={cn('w-3 h-3 transition-transform', reorderExpandedProject === project.id && 'rotate-90')} />
                        </button>
                      )}
                      <button
                        onClick={() => moveProject(pi, 'up')}
                        disabled={pi === 0}
                        className="p-1 rounded-md text-gray-500 hover:text-gray-200 hover:bg-gray-700/50 disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
                      >
                        <ChevronUp className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => moveProject(pi, 'down')}
                        disabled={pi === projects.length - 1}
                        className="p-1 rounded-md text-gray-500 hover:text-gray-200 hover:bg-gray-700/50 disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
                      >
                        <ChevronDown className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {reorderExpandedProject === project.id && project.chats.length > 0 && (
                    <div className="mx-2 mb-2 ml-7 space-y-0.5 border-l-2 border-gray-700/40 pl-2">
                      {project.chats.map((chat, ci) => (
                        <div
                          key={chat.id}
                          draggable
                          onDragStart={(e) => {
                            e.stopPropagation();
                            setDragChatKey({ projectId: project.id, chatIndex: ci });
                            e.dataTransfer.effectAllowed = 'move';
                          }}
                          onDragEnd={(e) => {
                            e.stopPropagation();
                            setDragChatKey(null);
                            setDragOverChatIndex(null);
                          }}
                          onDragOver={(e) => {
                            e.stopPropagation();
                            e.preventDefault();
                            if (dragChatKey !== null && ci !== dragChatKey.chatIndex) setDragOverChatIndex(ci);
                          }}
                          onDrop={(e) => {
                            e.stopPropagation();
                            handleChatDrop(e, project.id, ci);
                          }}
                          className={cn(
                            'flex items-center gap-2 px-2.5 py-1.5 rounded-lg transition-all duration-150',
                            dragOverChatIndex === ci && dragChatKey?.projectId === project.id
                              ? 'bg-aqua-500/10 border border-aqua-400/40 shadow-sm shadow-aqua-500/10'
                              : 'bg-gray-800/40 border border-transparent',
                            dragChatKey?.projectId === project.id && dragChatKey?.chatIndex === ci && 'opacity-40'
                          )}
                        >
                          <div className="cursor-grab active:cursor-grabbing p-0.5 rounded hover:bg-gray-700/50 transition-colors">
                            <GripVertical className="w-3 h-3 text-gray-500 hover:text-aqua-400 transition-colors" />
                          </div>
                          <MessageSquare className="w-3 h-3 text-gray-500 flex-shrink-0" />
                          <span className="text-xs text-gray-300 truncate flex-1">{chat.title}</span>
                          <div className="flex items-center gap-0.5 flex-shrink-0">
                            <button
                              onClick={() => moveChat(project.id, ci, 'up')}
                              disabled={ci === 0}
                              className="p-0.5 rounded text-gray-500 hover:text-gray-200 hover:bg-gray-700/50 disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
                            >
                              <ChevronUp className="w-3 h-3" />
                            </button>
                            <button
                              onClick={() => moveChat(project.id, ci, 'down')}
                              disabled={ci === project.chats.length - 1}
                              className="p-0.5 rounded text-gray-500 hover:text-gray-200 hover:bg-gray-700/50 disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
                            >
                              <ChevronDown className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
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
              {!reorderMode ? (
                <button onClick={() => setReorderMode(true)} className="text-gray-500 hover:text-gray-300 transition-colors text-[11px]">
                  Re-order
                </button>
              ) : (
                <button
                  onClick={() => {
                    setReorderMode(false);
                    setReorderExpandedProject(null);
                  }}
                  className="text-aqua-400 hover:text-aqua-300 transition-colors text-[11px]"
                >
                  Done
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {showNewModal && (
        <div className="absolute inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div
            ref={modalRef}
            className="w-full max-w-sm bg-gray-850 border border-gray-700/60 rounded-2xl shadow-2xl shadow-black/50 overflow-hidden"
          >
            {newModalStep === 'choose' && (
              <>
                <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700/40">
                  <h3 className="text-sm font-semibold text-gray-200">Create New</h3>
                  <button
                    onClick={closeNewModal}
                    className="p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 rounded-lg transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="p-4 space-y-2.5">
                  <button
                    onClick={async () => {
                      setNewModalStep('project');
                      await fs.load();
                    }}
                    className="w-full flex items-center gap-3 px-4 py-3.5 bg-gray-800 hover:bg-gray-750 border border-gray-700/50 hover:border-aqua-500/30 rounded-xl transition-all group"
                  >
                    <div className="w-9 h-9 rounded-lg bg-aqua-500/10 border border-aqua-500/20 flex items-center justify-center group-hover:bg-aqua-500/20 transition-colors">
                      <FolderPlus className="w-4.5 h-4.5 text-aqua-400" />
                    </div>
                    <div className="text-left">
                      <div className="text-sm font-medium text-gray-200">New Project</div>
                      <div className="text-[11px] text-gray-500">Create a new project from a folder</div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-gray-600 ml-auto" />
                  </button>
                  <button
                    onClick={() => setNewModalStep('chat')}
                    className="w-full flex items-center gap-3 px-4 py-3.5 bg-gray-800 hover:bg-gray-750 border border-gray-700/50 hover:border-aqua-500/30 rounded-xl transition-all group"
                  >
                    <div className="w-9 h-9 rounded-lg bg-aqua-500/10 border border-aqua-500/20 flex items-center justify-center group-hover:bg-aqua-500/20 transition-colors">
                      <MessageSquarePlus className="w-4.5 h-4.5 text-aqua-400" />
                    </div>
                    <div className="text-left">
                      <div className="text-sm font-medium text-gray-200">New Chat</div>
                      <div className="text-[11px] text-gray-500">Start a conversation in a project</div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-gray-600 ml-auto" />
                  </button>
                </div>
              </>
            )}

            {newModalStep === 'project' && (
              <>
                <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-700/40">
                  <button
                    onClick={() => setNewModalStep('choose')}
                    className="p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 rounded-lg transition-colors"
                  >
                    <ArrowLeft className="w-4 h-4" />
                  </button>
                  <h3 className="text-sm font-semibold text-gray-200">New Project</h3>
                  <div className="flex-1" />
                  <button
                    onClick={closeNewModal}
                    className="p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 rounded-lg transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="p-4 space-y-3">
                  <div>
                    <label className="block text-[11px] font-medium text-gray-400 mb-1.5">Project Name</label>
                    <input
                      type="text"
                      value={newProjectName}
                      onChange={(e) => setNewProjectName(e.target.value)}
                      placeholder="my-awesome-project"
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-700/50 rounded-xl text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-aqua-500/50 focus:ring-1 focus:ring-aqua-500/20 transition-all"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-gray-400 mb-1.5">Target Folder</label>

                    {newProjectPath && (
                      <div className="flex items-center gap-2 mb-2 px-3 py-1.5 bg-aqua-500/10 border border-aqua-500/20 rounded-lg">
                        <Check className="w-3 h-3 text-aqua-400 flex-shrink-0" />
                        <span className="text-xs font-mono text-aqua-300 truncate">{newProjectPath}</span>
                        <button onClick={() => setNewProjectPath('')} className="ml-auto p-0.5 text-aqua-400 hover:text-aqua-300">
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    )}

                    <div className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 border border-gray-700/50 rounded-t-xl text-[11px] font-mono text-gray-400">
                      <span className="truncate">{fs.path || 'Loading...'}</span>
                    </div>

                    <div className="bg-gray-800 border border-t-0 border-gray-700/50 rounded-b-xl max-h-40 overflow-y-auto">
                      {fs.loading && <div className="px-3 py-2 text-xs text-gray-500">Loading directories...</div>}
                      {fs.error && <div className="px-3 py-2 text-xs text-red-400">{fs.error}</div>}
                      {fs.data?.parentPath && (
                        <button
                          onClick={() => fs.load(fs.data?.parentPath ?? undefined)}
                          className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-400 hover:bg-gray-750 hover:text-gray-200 transition-colors"
                        >
                          <ArrowLeft className="w-3 h-3" />
                          <span>..</span>
                        </button>
                      )}
                      {currentFolders.map((folder) => (
                        <button
                          key={folder.path}
                          onClick={() => fs.load(folder.path)}
                          className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-750 hover:text-gray-100 transition-colors group"
                        >
                          <Folder className="w-3 h-3 text-aqua-400/60 flex-shrink-0" />
                          <span className="flex-1 text-left truncate">{folder.name}</span>
                          {folder.hasChildren && (
                            <ChevronRight className="w-3 h-3 text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                          )}
                        </button>
                      ))}
                    </div>

                    <button
                      onClick={() => setNewProjectPath(fs.path)}
                      disabled={!fs.path}
                      className="mt-2 w-full py-1.5 text-[11px] font-medium text-aqua-400 bg-aqua-500/10 hover:bg-aqua-500/15 border border-aqua-500/20 rounded-lg transition-colors disabled:opacity-40"
                    >
                      Select current folder
                    </button>
                  </div>

                  <button
                    onClick={handleCreateProject}
                    disabled={!newProjectName.trim() || !newProjectPath}
                    className="w-full py-2.5 text-sm font-medium text-gray-950 bg-aqua-500 hover:bg-aqua-400 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-colors shadow-lg shadow-aqua-500/20"
                  >
                    Create Project
                  </button>
                </div>
              </>
            )}

            {newModalStep === 'chat' && (
              <>
                <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-700/40">
                  <button
                    onClick={() => setNewModalStep('choose')}
                    className="p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 rounded-lg transition-colors"
                  >
                    <ArrowLeft className="w-4 h-4" />
                  </button>
                  <h3 className="text-sm font-semibold text-gray-200">New Chat</h3>
                  <div className="flex-1" />
                  <button
                    onClick={closeNewModal}
                    className="p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 rounded-lg transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="p-4 space-y-3">
                  <div>
                    <label className="block text-[11px] font-medium text-gray-400 mb-1.5">Project</label>
                    <select
                      value={newChatProjectId}
                      onChange={(e) => setNewChatProjectId(e.target.value)}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-700/50 rounded-xl text-sm text-gray-200 focus:outline-none focus:border-aqua-500/50 focus:ring-1 focus:ring-aqua-500/20 transition-all appearance-none"
                    >
                      <option value="" className="bg-gray-800 text-gray-400">
                        Select a project...
                      </option>
                      {projects.map((p) => (
                        <option key={p.id} value={p.id} className="bg-gray-800">
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-gray-400 mb-1.5">Chat Title</label>
                    <input
                      type="text"
                      value={newChatTitle}
                      onChange={(e) => setNewChatTitle(e.target.value)}
                      placeholder="e.g. Add authentication flow"
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-700/50 rounded-xl text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-aqua-500/50 focus:ring-1 focus:ring-aqua-500/20 transition-all"
                    />
                  </div>

                  <button
                    onClick={handleCreateChat}
                    disabled={!newChatTitle.trim() || !newChatProjectId}
                    className="w-full py-2.5 text-sm font-medium text-gray-950 bg-aqua-500 hover:bg-aqua-400 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-colors shadow-lg shadow-aqua-500/20"
                  >
                    Create Chat
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ChatListItem({
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
}: {
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
}) {
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div
      className="relative"
      onMouseEnter={onMouseEnter}
      onMouseLeave={() => {
        onMouseLeave();
        setShowMenu(false);
      }}
    >
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
          isActive ? 'bg-aqua-500/10 border border-aqua-500/20 shadow-sm' : 'hover:bg-gray-800/50 border border-transparent'
        )}
      >
        {isActive && <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-aqua-400 rounded-r-full" />}

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
        <div className="absolute right-2 top-full z-20 mt-1 w-36 bg-gray-800 border border-gray-700/60 rounded-xl shadow-xl shadow-black/40 py-1 overflow-hidden">
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
            onClick={() => {
              if (window.confirm('Delete this chat?')) onDelete?.(chat.id);
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
