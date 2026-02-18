import { useState, useCallback, useRef, useEffect } from 'react';
import { ChatPanel } from './components/chat/ChatPanel';
import { ActionsPanel } from './components/ActionsPanel';
import { AppHeader } from './components/header/AppHeader';
import { ResizableLayout } from './components/layout/ResizableLayout';
import { EnhancedModelPicker } from './components/EnhancedModelPicker';
import { SettingsModal } from './components/SettingsModal';
import { useToast } from './hooks/useToast';
import { useChatHistory, useProjects, useSettings, useAgentEvents } from './api';
import type { AgentEvent, AutoApproveRule } from './api';

export function App() {
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [settingsTab, setSettingsTab] = useState<'openrouter' | 'agent' | null>(null);
  const [chatWidth, setChatWidth] = useState(33.33);
  const { showNotification, notificationMessage, showToast } = useToast();
  const [processingChats, setProcessingChats] = useState<Set<string>>(new Set());

  const isProcessing = activeChatId != null && processingChats.has(activeChatId);

  // ── API hooks ──────────────────────────────────────────────────
  const chat = useChatHistory(activeChatId);
  const projectsApi = useProjects();
  const { projects, loading: projectsLoading } = projectsApi;
  const settings = useSettings();

  // Bootstrap activeChatId from first available chat when projects load
  useEffect(() => {
    if (projectsLoading) return;
    const allChats = projects.flatMap((p) => p.chats);
    const firstChatId = allChats[0]?.id ?? null;
    const currentExists = activeChatId != null && allChats.some((c) => c.id === activeChatId);
    if (!currentExists) {
      setActiveChatId(firstChatId);
    }
  }, [projectsLoading, projects, activeChatId]);

  const setProcessingChatsRef = useRef(setProcessingChats);
  setProcessingChatsRef.current = setProcessingChats;

  const removeProcessing = useCallback((chatIdToRemove: string) => {
    setProcessingChatsRef.current((prev) => {
      const next = new Set(prev);
      next.delete(chatIdToRemove);
      return next;
    });
  }, []);

  const handleAgentEvent = useCallback(
    (event: AgentEvent) => {
      if (event.type === 'chat_title_updated') {
        projectsApi.refresh();
        return;
      }
      if (
        event.type === 'agent_done' ||
        (event.type === 'error' && !(event.payload as { toolCallId?: string })?.toolCallId)
      ) {
        removeProcessing(event.chatId);
        return;
      }
      if (event.chatId !== activeChatId) return;
      chat.processEvent(event);
    },
    [activeChatId, chat, projectsApi, removeProcessing],
  );

  useAgentEvents([activeChatId, ...processingChats], handleAgentEvent);

  // ── Actions that go through the API ────────────────────────────

  const handleSendMessage = async (content: string) => {
    if (activeChatId == null) return;
    const chatIdToProcess = activeChatId;
    setProcessingChats((prev) => new Set(prev).add(chatIdToProcess));

    const res = await chat.sendMessage(content);
    if (!res.ok) {
      showToast(`Error: ${res.error}`);
      setProcessingChats((prev) => {
        const next = new Set(prev);
        next.delete(chatIdToProcess);
        return next;
      });
    }
  };

  const handleApproveCommand = async (toolCallId: string) => {
    const res = await chat.approveCommand(toolCallId);
    if (res.ok) showToast('Tool call approved');
    else showToast(`Error: ${res.error}`);
  };

  const handleRejectCommand = async (toolCallId: string) => {
    const res = await chat.rejectCommand(toolCallId);
    if (res.ok) showToast('Tool call rejected');
    else showToast(`Error: ${res.error}`);
  };

  const handleRevertToCheckpoint = async (checkpointId: string) => {
    const cp = chat.checkpoints.find((c) => c.id === checkpointId);
    const res = await chat.revertToCheckpoint(checkpointId);
    if (res.ok) showToast(`Reverted to checkpoint: ${cp?.label ?? checkpointId}`);
    else showToast(`Error: ${res.error}`);
  };

  const handleRevertFile = async (fileEditId: string) => {
    const fe = chat.fileEdits.find((f) => f.id === fileEditId);
    const res = await chat.revertFile(fileEditId);
    if (res.ok) showToast(`Reverted file: ${fe?.filePath ?? fileEditId}`);
    else showToast(`Error: ${res.error}`);
  };

  const handleEditMessage = (messageId: string, newContent: string) => {
    if (!window.confirm('This will revert all changes after this message and re-run the agent with the new content. Continue?')) {
      return;
    }
    setProcessingChats((prev) => new Set(prev).add(activeChatId!));
    chat.editMessage(messageId, newContent).then((res) => {
      if (res.ok) showToast('Message updated — re-running agent');
      else {
        showToast(`Error: ${res.error}`);
        setProcessingChats((prev) => {
          const next = new Set(prev);
          if (activeChatId) next.delete(activeChatId);
          return next;
        });
      }
    });
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd/Ctrl + K to open model picker
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShowModelPicker(true);
      }
      // Cmd/Ctrl + , to open settings
      if ((e.metaKey || e.ctrlKey) && e.key === ',') {
        e.preventDefault();
        setSettingsTab('openrouter');
      }
    };

    globalThis.addEventListener('keydown', handleKeyDown);
    return () => globalThis.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSwitchChat = (chatId: string) => {
    setActiveChatId(chatId);
  };

  const handleCreateProject = async (name: string, path: string) => {
    const res = await projectsApi.createProject(name, path);
    if (!res.ok) showToast(`Error: ${res.error}`);
  };

  const handleCreateChat = async (projectId: string, title?: string) => {
    const res = await projectsApi.createChat(projectId, title);
    if (res.ok) {
      setActiveChatId(res.data.chat.id);
      showToast('Chat created');
    } else {
      showToast(`Error: ${res.error}`);
    }
  };

  const handleRenameChat = async (chatId: string, title: string) => {
    const res = await projectsApi.renameChat(chatId, title);
    if (!res.ok) showToast(`Error: ${res.error}`);
  };

  const handlePinChat = async (chatId: string, isPinned: boolean) => {
    const res = await projectsApi.pinChat(chatId, isPinned);
    if (!res.ok) showToast(`Error: ${res.error}`);
  };

  const handleDeleteChat = async (chatId: string) => {
    const res = await projectsApi.deleteChat(chatId);
    if (res.ok) {
      if (chatId === activeChatId) {
        setActiveChatId(res.data.fallbackChatId ?? null);
      }
      showToast('Chat deleted');
    } else {
      showToast(`Error: ${res.error}`);
    }
  };

  const handleReorderProjects = async (projectIds: string[]) => {
    const res = await projectsApi.reorderProjects(projectIds);
    if (!res.ok) showToast(`Error: ${res.error}`);
  };

  const handleReorderChats = async (projectId: string, chatIds: string[]) => {
    const res = await projectsApi.reorderChats(projectId, chatIds);
    if (!res.ok) showToast(`Error: ${res.error}`);
  };

  const handleDeleteProject = async (projectId: string) => {
    const project = projects.find((p) => p.id === projectId);
    const hadActiveChat = project?.chats.some((c) => c.id === activeChatId);
    const res = await projectsApi.deleteProject(projectId);
    if (res.ok) {
      if (hadActiveChat) setActiveChatId(null);
      showToast('Project deleted');
    } else {
      showToast(`Error: ${res.error}`);
    }
  };

  const handleUpdateAutoApproveRules = async (rules: Omit<AutoApproveRule, 'id' | 'createdAt'>[]) => {
    const res = await settings.updateAutoApproveRules(rules);
    if (!res.ok) {
      showToast(`Error: ${res.error}`);
    }
  };

  const currentProject =
    activeChatId == null
      ? undefined
      : projects.find((p) => p.chats.some((c) => c.id === activeChatId));
  const currentProjectChats = [...(currentProject?.chats ?? [])].sort((a, b) => {
    if (a.isPinned && !b.isPinned) return -1;
    if (!a.isPinned && b.isPinned) return 1;
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  });

  if (projectsLoading) {
    return (
      <div className="h-screen w-screen bg-gray-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-aqua-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-gray-400">Loading…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen bg-gray-950 text-white flex flex-col overflow-hidden">
      <AppHeader
        currentProjectChats={currentProjectChats}
        activeChatId={activeChatId}
        processingChats={processingChats}
        currentProjectId={currentProject?.id}
        onSwitchChat={handleSwitchChat}
        onReorderChats={handleReorderChats}
        onOpenModelPicker={() => setShowModelPicker(true)}
        onPrefetchSettings={settings.prefetchSettings}
        currentModel={settings.currentModel}
        onSelectSettingsProvider={setSettingsTab}
        projectsLoading={projectsLoading}
        chatLoading={chat.loading}
      />

      <ResizableLayout
        chatWidth={chatWidth}
        onChatWidthChange={setChatWidth}
        leftPanel={
          <ChatPanel
            messages={chat.messages}
            checkpoints={chat.checkpoints}
            chatLoading={chat.loading}
            onRevert={handleRevertToCheckpoint}
            contextItems={chat.contextItems}
            maxTokens={chat.maxTokens}
            onSendMessage={handleSendMessage}
            projects={projects}
            activeChatId={activeChatId}
            onSwitchChat={handleSwitchChat}
            isProcessing={isProcessing}
            onCreateProject={handleCreateProject}
            onCreateChat={handleCreateChat}
            onRenameChat={handleRenameChat}
            onPinChat={handlePinChat}
            onDeleteChat={handleDeleteChat}
            onReorderProjects={handleReorderProjects}
            onReorderChats={handleReorderChats}
            onDeleteProject={handleDeleteProject}
            onEditMessage={activeChatId != null ? handleEditMessage : undefined}
          />
        }
        rightPanel={
          <ActionsPanel
            toolCalls={chat.toolCalls}
            fileEdits={chat.fileEdits}
            checkpoints={chat.checkpoints}
            reasoningBlocks={chat.reasoningBlocks}
            streamingReasoningBlockIds={chat.streamingReasoningBlockIds}
            onRevertFile={handleRevertFile}
            onRevertCheckpoint={handleRevertToCheckpoint}
            onApproveCommand={handleApproveCommand}
            onRejectCommand={handleRejectCommand}
            autoApproveRules={settings.autoApproveRules}
            onUpdateAutoApproveRules={handleUpdateAutoApproveRules}
          />
        }
      />

      {/* Toast */}
      {showNotification && (
        <div className="fixed bottom-4 right-4 px-4 py-3 bg-gray-800 border border-gray-700/50 rounded-xl shadow-2xl shadow-black/50 animate-in slide-in-from-bottom-2 fade-in duration-200">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-aqua-400" />
            <p className="text-sm text-gray-200">{notificationMessage}</p>
          </div>
        </div>
      )}

      {/* Modals — always mounted so opening is instant (no mount delay) */}
      <EnhancedModelPicker
        visible={showModelPicker}
        onClose={() => setShowModelPicker(false)}
        currentModel={settings.currentModel}
        modelsByProvider={settings.modelsByProvider}
        modelMetadata={settings.modelMetadata}
        loading={settings.loading}
        changeModel={settings.changeModel}
      />
      <SettingsModal
        visible={settingsTab != null}
        onClose={() => setSettingsTab(null)}
        initialTab={settingsTab}
      />
    </div>
  );
}
