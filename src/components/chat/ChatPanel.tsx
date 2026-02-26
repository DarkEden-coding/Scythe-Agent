import { useState, useEffect, useCallback } from 'react';
import { useHashTab } from '@/hooks/useHashTab';
import { useAutoScroll } from '@/hooks/useAutoScroll';
import {
  MessageSquare,
  FolderOpen,
  Folder,
  Plus,
  AlertTriangle,
  RotateCcw,
  MessageCircleQuestion,
} from 'lucide-react';
import type {
  Message,
  Checkpoint,
  ContextItem,
  Project,
  ProjectChat,
  VerificationIssues,
  ObservationData,
} from '@/types';
import { ContextDropdown } from '@/components/ContextDropdown';
import { NewEntityModal } from '@/components/projects/NewEntityModal';
import { DeleteChatConfirmModal } from '@/components/projects/DeleteChatConfirmModal';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { ObservationStatusIndicator } from './ObservationStatusIndicator';
import { ProjectsTab } from '@/components/projects/ProjectsTab';
import { cn } from '@/utils/cn';
import type { ObservationStatus } from './ObservationStatusIndicator';

interface ChatPanelProps {
  readonly messages: Message[];
  readonly checkpoints: Checkpoint[];
  readonly chatLoading?: boolean;
  readonly onRevert: (checkpointId: string) => void;
  readonly contextItems: ContextItem[];
  readonly maxTokens: number;
  readonly onSendMessage?: (
    content: string,
    options?: {
      mode?: 'default' | 'planning' | 'plan_edit';
      activePlanId?: string;
      referencedFiles?: string[];
    },
  ) => void;
  readonly onCancel?: () => void;
  readonly projects: Project[];
  readonly activeChatId?: string | null;
  readonly activePlanId?: string | null;
  readonly onSwitchChat?: (chatId: string) => void;
  readonly isProcessing?: boolean;
  readonly onCreateProject?: (name: string, path: string) => Promise<void> | void;
  readonly onCreateChat?: (projectId: string, title?: string) => Promise<void> | void;
  readonly onRenameChat?: (chatId: string, title: string) => Promise<void> | void;
  readonly onPinChat?: (chatId: string, isPinned: boolean) => Promise<void> | void;
  readonly onDeleteChat?: (chatId: string) => Promise<void> | void;
  readonly onReorderProjects?: (projectIds: string[]) => Promise<void> | void;
  readonly onReorderChats?: (projectId: string, chatIds: string[]) => Promise<void> | void;
  readonly onDeleteProject?: (projectId: string) => Promise<void> | void;
  readonly onEditMessage?: (messageId: string, newContent: string, referencedFiles?: string[]) => void;
  readonly verificationIssues?: Record<string, VerificationIssues>;
  readonly observationStatus?: ObservationStatus;
  readonly observation?: ObservationData | null;
  readonly observations?: ObservationData[];
  readonly showObservationsInChat?: boolean;
  readonly persistentError?: {
    message: string;
    source?: string;
    retryable?: boolean;
    retryAction?: string;
  } | null;
  readonly onRetryPersistentError?: () => void | Promise<void>;
  readonly awaitingUserQuery?: { query: string } | null;
  readonly userQueriesByCheckpoint?: Record<string, string>;
}

export function ChatPanel({
  messages,
  checkpoints,
  chatLoading = false,
  onRevert,
  contextItems,
  maxTokens,
  onSendMessage,
  onCancel,
  projects,
  activeChatId: externalActiveChatId,
  activePlanId = null,
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
  onEditMessage,
  verificationIssues = {},
  observationStatus = 'idle',
  observation = null,
  observations = [],
  showObservationsInChat = false,
  persistentError = null,
  onRetryPersistentError,
  awaitingUserQuery = null,
  userQueriesByCheckpoint = {},
}: ChatPanelProps) {
  const [inputValue, setInputValue] = useState('');
  const [inputReferencedFiles, setInputReferencedFiles] = useState<string[]>([]);
  const [composeMode, setComposeMode] = useState<'default' | 'planning'>('default');
  const [activeTab, setActiveTab] = useHashTab<'chat' | 'projects'>('chat', ['chat', 'projects']);
  const [activeChatId, setActiveChatId] = useState(externalActiveChatId ?? null);
  const [showNewModal, setShowNewModal] = useState(false);
  const [chatToDelete, setChatToDelete] = useState<ProjectChat | null>(null);
  const [deleteInProgress, setDeleteInProgress] = useState(false);

  const chatScroll = useAutoScroll(messages, { enabled: activeTab === 'chat' });

  useEffect(() => {
    setActiveChatId(externalActiveChatId ?? null);
    setInputValue('');
    setInputReferencedFiles([]);
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
    const options = composeMode === 'planning'
      ? {
          mode: activePlanId ? ('plan_edit' as const) : ('planning' as const),
          activePlanId: activePlanId ?? undefined,
          referencedFiles: inputReferencedFiles,
        }
      : { referencedFiles: inputReferencedFiles };
    onSendMessage?.(inputValue.trim(), options);
    setInputValue('');
    setInputReferencedFiles([]);
  };

  const currentProject = activeChatId
    ? projects.find((p) => p.chats.some((c) => c.id === activeChatId))
    : undefined;

  const openNewModal = async () => {
    setShowNewModal(true);
  };

  const handleCreateChatAndSwitch = useCallback(
    async (projectId: string, title?: string) => {
      await onCreateChat?.(projectId, title);
      setActiveTab('chat');
    },
    [onCreateChat],
  );

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
              <ObservationStatusIndicator status={observationStatus} />
              <ContextDropdown
                contextItems={contextItems}
                maxTokens={maxTokens}
                chatId={activeChatId}
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
          {persistentError && (
            <div className="mx-4 mt-3 px-3 py-2.5 rounded-xl border border-red-500/40 bg-red-500/10">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2 min-w-0">
                  <AlertTriangle className="w-4 h-4 text-red-300 mt-0.5 shrink-0" />
                  <p className="text-xs text-red-100 break-words">{persistentError.message}</p>
                </div>
                {persistentError.retryable && persistentError.retryAction === 'retry_observation' && (
                  <button
                    type="button"
                    onClick={() => onRetryPersistentError?.()}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] bg-red-500/20 border border-red-400/40 text-red-100 hover:bg-red-500/30 transition-colors shrink-0"
                  >
                    <RotateCcw className="w-3 h-3" />
                    Retry
                  </button>
                )}
              </div>
            </div>
          )}
          <div
            ref={chatScroll.ref}
            onScroll={chatScroll.onScroll}
            className="flex-1 overflow-y-auto p-4 space-y-4 relative"
          >
            {chatLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-900/50 z-10">
                <div className="w-6 h-6 border-2 border-aqua-400 border-t-transparent rounded-full animate-spin" />
              </div>
            )}
            <MessageList
              messages={messages}
              activeChatId={activeChatId}
              isProcessing={isProcessing ?? false}
              onRevert={onRevert}
              onEditMessage={onEditMessage}
              getCheckpointForMessage={getCheckpointForMessage}
              verificationIssues={verificationIssues}
              observation={observation}
              observations={observations}
              showObservationsInChat={showObservationsInChat}
              userQueriesByCheckpoint={userQueriesByCheckpoint}
            />
          </div>
          {awaitingUserQuery && (
            <div className="px-4 pb-2">
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 flex items-start gap-3">
                <MessageCircleQuestion className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] uppercase tracking-wider text-amber-400/80 font-medium mb-1">
                    Agent is waiting for your response
                  </p>
                  <p className="text-sm text-amber-100/90 leading-relaxed whitespace-pre-wrap">
                    {awaitingUserQuery.query || 'No question provided.'}
                  </p>
                </div>
              </div>
            </div>
          )}
          <div className="p-3 border-t border-gray-700/40 bg-gray-850">
            <MessageInput
              value={inputValue}
              onChange={setInputValue}
              referencedFiles={inputReferencedFiles}
              onReferencedFilesChange={setInputReferencedFiles}
              onSubmit={handleSend}
              onCancel={onCancel}
              composeMode={composeMode}
              onComposeModeChange={setComposeMode}
              activeChatId={activeChatId}
              activeProjectPath={currentProject?.path ?? null}
              isProcessing={isProcessing}
            />
          </div>
        </>
      )}

      {activeTab === 'projects' && (
        <ProjectsTab
          projects={projects}
          activeChatId={activeChatId}
          onSelectChat={handleSelectChat}
          onCreateChat={handleCreateChatAndSwitch}
          onRenameChat={onRenameChat}
          onPinChat={onPinChat}
          onDeleteChat={onDeleteChat}
          onRequestDeleteChat={(chat) => setChatToDelete(chat)}
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
        onCreateChat={handleCreateChatAndSwitch}
      />
      <DeleteChatConfirmModal
        visible={chatToDelete != null}
        chatTitle={chatToDelete?.title ?? ''}
        onClose={() => setChatToDelete(null)}
        onConfirm={async () => {
          if (!chatToDelete) return;
          setDeleteInProgress(true);
          try {
            await onDeleteChat?.(chatToDelete.id);
            setChatToDelete(null);
          } finally {
            setDeleteInProgress(false);
          }
        }}
        loading={deleteInProgress}
      />
    </div>
  );
}
