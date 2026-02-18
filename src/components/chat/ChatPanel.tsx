import { useState, useEffect } from 'react';
import { useHashTab } from '@/hooks/useHashTab';
import {
  MessageSquare,
  FolderOpen,
  Folder,
  Plus,
} from 'lucide-react';
import type { Message, Checkpoint, ContextItem, Project } from '@/types';
import { ContextDropdown } from '@/components/ContextDropdown';
import { NewEntityModal } from '@/components/projects/NewEntityModal';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { ProjectsTab } from '@/components/projects/ProjectsTab';
import { cn } from '@/utils/cn';

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
  activeChatId?: string | null;
  onSwitchChat?: (chatId: string) => void;
  isProcessing?: boolean;
  onCreateProject?: (name: string, path: string) => Promise<void> | void;
  onCreateChat?: (projectId: string, title?: string) => Promise<void> | void;
  onRenameChat?: (chatId: string, title: string) => Promise<void> | void;
  onPinChat?: (chatId: string, isPinned: boolean) => Promise<void> | void;
  onDeleteChat?: (chatId: string) => Promise<void> | void;
  onReorderProjects?: (projectIds: string[]) => Promise<void> | void;
  onReorderChats?: (projectId: string, chatIds: string[]) => Promise<void> | void;
  onDeleteProject?: (projectId: string) => Promise<void> | void;
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
  onDeleteProject,
}: ChatPanelProps) {
  const [inputValue, setInputValue] = useState('');
  const [activeTab, setActiveTab] = useHashTab<'chat' | 'projects'>('chat', ['chat', 'projects']);
  const [activeChatId, setActiveChatId] = useState(externalActiveChatId ?? null);
  const [showNewModal, setShowNewModal] = useState(false);

  useEffect(() => {
    setActiveChatId(externalActiveChatId ?? null);
  }, [externalActiveChatId]);

  const getCheckpointForMessage = (messageId: string) =>
    checkpoints.find((cp) => cp.messageId === messageId);

  const handleSelectChat = (chatId: string) => {
    setActiveChatId(chatId);
    onSwitchChat?.(chatId);
    setActiveTab('chat');
  };

  const handleSend = () => {
    if (!inputValue.trim() || !activeChatId) return;
    onSendMessage?.(inputValue.trim());
    setInputValue('');
  };

  const currentProject = activeChatId
    ? projects.find((p) => p.chats.some((c) => c.id === activeChatId))
    : undefined;

  const openNewModal = async () => {
    setShowNewModal(true);
  };

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
                  : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800/50',
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
                  : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800/50',
              )}
            >
              <FolderOpen className="w-3.5 h-3.5" />
              Projects
              <span
                className={cn(
                  'text-[10px] px-1.5 py-0.5 rounded-full',
                  activeTab === 'projects' ? 'bg-aqua-500/20 text-aqua-400' : 'bg-gray-700/50 text-gray-500',
                )}
              >
                {projects.length}
              </span>
            </button>
          </div>

          {activeTab === 'chat' && (
            <div className="flex items-center gap-2">
              {currentProject && (
                <div className="flex items-center gap-0.5">
                  <button
                    type="button"
                    onClick={() => onCreateChat?.(currentProject.id)}
                    title="New chat in this project"
                    className="flex items-center justify-center w-5 h-5 rounded text-aqua-400 hover:bg-aqua-500/20 hover:text-aqua-300 transition-colors"
                  >
                    <Plus className="w-3 h-3" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab('projects')}
                    title="Go to projects"
                    className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-gray-750/80 border border-gray-700/50 text-[11px] text-gray-400 hover:bg-gray-700/60 hover:text-gray-300 transition-colors cursor-pointer"
                  >
                    <Folder className="w-3 h-3 text-aqua-400/70" />
                    {currentProject.name}
                  </button>
                </div>
              )}
              <ContextDropdown
                contextItems={contextItems}
                maxTokens={maxTokens}
                onSummarize={onSummarize}
                onRemoveItem={onRemoveContextItem}
              />
            </div>
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
            <MessageList
              messages={messages}
              activeChatId={activeChatId}
              isProcessing={isProcessing ?? false}
              onRevert={onRevert}
              getCheckpointForMessage={getCheckpointForMessage}
            />
          </div>
          <div className="p-3 border-t border-gray-700/40 bg-gray-850">
            <MessageInput
              value={inputValue}
              onChange={setInputValue}
              onSubmit={handleSend}
              activeChatId={activeChatId}
            />
          </div>
        </>
      )}

      {activeTab === 'projects' && (
        <ProjectsTab
          projects={projects}
          activeChatId={activeChatId}
          onSelectChat={handleSelectChat}
          onCreateChat={onCreateChat}
          onRenameChat={onRenameChat}
          onPinChat={onPinChat}
          onDeleteChat={onDeleteChat}
          onReorderProjects={onReorderProjects}
          onReorderChats={onReorderChats}
          onDeleteProject={onDeleteProject}
        />
      )}

      <NewEntityModal
        visible={showNewModal}
        onClose={() => setShowNewModal(false)}
        projects={projects}
        onCreateProject={onCreateProject}
        onCreateChat={onCreateChat}
      />
    </div>
  );
}
