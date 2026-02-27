import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { ChatPanel } from './components/chat/ChatPanel';
import { ActionsPanel } from './components/ActionsPanel';
import { AppHeader } from './components/header/AppHeader';
import { ResizableLayout } from './components/layout/ResizableLayout';
import { EnhancedModelPicker } from './components/EnhancedModelPicker';
import { SettingsModal } from './components/SettingsModal';
import { Modal } from './components/Modal';
import { useToast } from './hooks/useToast';
import { api, useChatHistory, useProjects, useSettings, useAgentEvents } from './api';
import type { AgentEvent, AgentPausePayload, AutoApproveRule } from './api';
import type { SettingsTabId } from './components/ProviderSettingsDropdown';

interface IterationLimitPauseState {
  chatId: string;
  checkpointId: string;
  iteration: number;
  maxIterations: number;
  message: string;
}

export function App() {
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [settingsTab, setSettingsTab] = useState<SettingsTabId | null>(null);
  const [chatWidth, setChatWidth] = useState(33.33);
  const [showObservationsInChat, setShowObservationsInChat] = useState(false);
  const { showNotification, notificationMessage, showToast } = useToast();
  const [processingChats, setProcessingChats] = useState<Set<string>>(new Set());
  const [iterationLimitPause, setIterationLimitPause] = useState<IterationLimitPauseState | null>(null);
  const [continuingPausedRun, setContinuingPausedRun] = useState(false);

  const isProcessing = activeChatId != null && processingChats.has(activeChatId);

  // ── API hooks ──────────────────────────────────────────────────
  const chat = useChatHistory(activeChatId);

  const awaitingUserQuery = useMemo(() => {
    if (isProcessing) return null;
    const last = chat.toolCalls.at(-1);
    if (last?.name !== 'user_query' || last?.status !== 'completed') return null;
    const q = last.input?.query;
    const queryStr =
      typeof q === 'string' ? q : q == null ? '' : typeof q === 'object' ? JSON.stringify(q) : String(q);
    return { query: queryStr };
  }, [isProcessing, chat.toolCalls]);

  const userQueriesByCheckpoint = useMemo(() => {
    const map: Record<string, string> = {};
    for (const tc of chat.toolCalls) {
      if (tc.name !== 'user_query' || tc.status !== 'completed') continue;
      const q = tc.input?.query;
      const queryStr =
        typeof q === 'string' ? q : q == null ? '' : typeof q === 'object' ? JSON.stringify(q) : String(q);
      const cp = chat.checkpoints.find((c) => c.toolCalls.includes(tc.id));
      if (cp && queryStr) map[cp.id] = queryStr;
    }
    return map;
  }, [chat.toolCalls, chat.checkpoints]);
  const projectsApi = useProjects();
  const { projects, loading: projectsLoading } = projectsApi;
  const settings = useSettings();

  // OAuth popup: when we load with ?openai-sub in a popup, notify opener and close
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get('openai-sub');
    if (status && window.opener) {
      window.opener.postMessage({ type: 'openai-sub-auth-done', status }, window.location.origin);
      window.close();
    }
  }, []);

  // OAuth popup: when opener receives auth-done, refresh settings (incl. model list) and notify OpenAISub panel
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.origin !== window.location.origin) return;
      const data = e.data;
      if (data?.type === 'openai-sub-auth-done') {
        settings.refreshSettings();
        window.dispatchEvent(new CustomEvent('openai-sub-auth-done', { detail: { status: data.status } }));
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [settings.refreshSettings]);

  // Fetch memory settings to know whether to show observations in chat
  useEffect(() => {
    api.getMemorySettings().then((res) => {
      if (res.ok) setShowObservationsInChat(!!res.data.show_observations_in_chat);
    });
  }, []);

  // Persist active chat so it restores on refresh (never clear — bootstrap may run before projects load)
  useEffect(() => {
    if (activeChatId) localStorage.setItem('activeChatId', activeChatId);
  }, [activeChatId]);

  // Bootstrap activeChatId from last opened or first available chat when projects load
  useEffect(() => {
    if (projectsLoading || !projects.length) return;
    const allChats = projects.flatMap((p) => p.chats);
    if (!allChats.length) return;
    const firstChatId = allChats[0]?.id ?? null;
    const lastChatId = localStorage.getItem('activeChatId');
    const lastExists = lastChatId && allChats.some((c) => c.id === lastChatId);
    const currentExists = activeChatId != null && allChats.some((c) => c.id === activeChatId);
    if (!currentExists) {
      setActiveChatId(lastExists ? lastChatId : firstChatId);
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
      if (event.type === 'agent_done') {
        removeProcessing(event.chatId);
      }
      if (event.type === 'agent_paused') {
        removeProcessing(event.chatId);
        const payload = event.payload as AgentPausePayload;
        if (payload.reason === 'max_iterations') {
          if (event.chatId === activeChatId) {
            setIterationLimitPause({
              chatId: event.chatId,
              checkpointId: payload.checkpointId,
              iteration: payload.iteration ?? payload.maxIterations ?? 0,
              maxIterations: payload.maxIterations ?? 0,
              message:
                payload.message ??
                'The agent reached its iteration limit and paused. Do you want to continue?',
            });
          }
        } else if (payload.reason === 'repetitive_tool_calls' && event.chatId === activeChatId) {
          showToast(
            payload.message ??
              'Agent paused after calling the same tool with similar arguments repeatedly.',
          );
        }
      }
      if (event.type === 'error' && !(event.payload as { toolCallId?: string })?.toolCallId) {
        removeProcessing(event.chatId);
        if (event.chatId === activeChatId) {
          const payload = event.payload as { message?: string };
          showToast(`Error: ${payload.message ?? 'Unknown error'}`);
        }
      }
      if (event.chatId !== activeChatId) return;
      chat.processEvent(event);
    },
    [activeChatId, chat, projectsApi, removeProcessing, showToast],
  );

  useAgentEvents([activeChatId, ...processingChats], handleAgentEvent);

  // ── Actions that go through the API ────────────────────────────

  const handleSendMessage = async (
    content: string,
    options?: {
      mode?: 'default' | 'planning' | 'plan_edit';
      activePlanId?: string;
      referencedFiles?: string[];
    },
  ) => {
    if (activeChatId == null) return;
    const chatIdToProcess = activeChatId;
    setProcessingChats((prev) => new Set(prev).add(chatIdToProcess));

    const res = await chat.sendMessage(content, options);
    if (!res.ok) {
      showToast(`Error: ${res.error}`);
      setProcessingChats((prev) => {
        const next = new Set(prev);
        next.delete(chatIdToProcess);
        return next;
      });
    }
  };

  const handleCancelMessage = useCallback(() => {
    if (activeChatId == null) return;
    chat.cancelProcessing(activeChatId);
    setProcessingChats((prev) => {
      const next = new Set(prev);
      next.delete(activeChatId);
      return next;
    });
  }, [activeChatId, chat]);

  const handleRetryObservation = useCallback(async () => {
    const res = await chat.retryObservation();
    if (!res.ok) showToast(`Error: ${res.error}`);
  }, [chat, showToast]);

  const handleContinuePausedRun = useCallback(async () => {
    if (iterationLimitPause == null) return;
    setContinuingPausedRun(true);
    setProcessingChats((prev) => new Set(prev).add(iterationLimitPause.chatId));
    const res = await chat.continueAgent();
    if (res.ok) {
      setIterationLimitPause(null);
      showToast('Continuing agent run');
    } else {
      showToast(`Error: ${res.error}`);
      setProcessingChats((prev) => {
        const next = new Set(prev);
        next.delete(iterationLimitPause.chatId);
        return next;
      });
    }
    setContinuingPausedRun(false);
  }, [chat, iterationLimitPause, showToast]);

  const handleApproveCommand = async (toolCallId: string) => {
    if (activeChatId != null) {
      setProcessingChats((prev) => new Set(prev).add(activeChatId));
    }
    const res = await chat.approveCommand(toolCallId);
    if (res.ok) showToast('Tool call approved');
    else {
      showToast(`Error: ${res.error}`);
      if (activeChatId != null) {
        setProcessingChats((prev) => {
          const next = new Set(prev);
          next.delete(activeChatId);
          return next;
        });
      }
    }
  };

  const handleRejectCommand = async (toolCallId: string) => {
    if (activeChatId != null) {
      setProcessingChats((prev) => new Set(prev).add(activeChatId));
    }
    const res = await chat.rejectCommand(toolCallId);
    if (res.ok) showToast('Tool call rejected');
    else {
      showToast(`Error: ${res.error}`);
      if (activeChatId != null) {
        setProcessingChats((prev) => {
          const next = new Set(prev);
          next.delete(activeChatId);
          return next;
        });
      }
    }
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

  const handleEditMessage = (messageId: string, newContent: string, referencedFiles?: string[]) => {
    if (!window.confirm('This will revert all changes after this message and re-run the agent with the new content. Continue?')) {
      return;
    }
    setProcessingChats((prev) => new Set(prev).add(activeChatId!));
    chat.editMessage(messageId, newContent, referencedFiles).then((res) => {
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

  const handleOpenImplementationChat = useCallback(
    async (chatId: string) => {
      await projectsApi.refresh();
      setActiveChatId(chatId);
      setProcessingChats((prev) => new Set(prev).add(chatId));
    },
    [projectsApi],
  );

  const handleSavePlan = useCallback(
    async (planId: string, content: string, baseRevision: number) => {
      const res = await chat.updatePlan(planId, content, {
        baseRevision,
        lastEditor: 'user',
      });
      if (!res.ok) {
        showToast(`Error: ${res.error}`);
      } else if (res.data.conflict) {
        showToast('Plan conflict detected. Refresh and retry.');
      } else {
        showToast('Plan updated');
      }
      return res;
    },
    [chat, showToast],
  );

  const handleApprovePlan = useCallback(
    async (planId: string, action: 'keep_context' | 'clear_context') => {
      const res = await chat.approvePlan(planId, action);
      if (!res.ok) {
        showToast(`Error: ${res.error}`);
        return res;
      }
      const implementationChatId = res.data.implementationChatId;
      if (action === 'keep_context' && activeChatId) {
        setProcessingChats((prev) => new Set(prev).add(activeChatId));
      }
      if (action === 'clear_context' && implementationChatId) {
        await handleOpenImplementationChat(implementationChatId);
      }
      showToast(
        action === 'keep_context'
          ? 'Approved plan and started implementation in current chat'
          : 'Approved plan and started implementation in a new chat',
      );
      return res;
    },
    [activeChatId, chat, handleOpenImplementationChat, showToast],
  );

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
  const activePlanId =
    [...chat.plans]
      .filter((plan) => !['approved', 'implementing', 'implemented'].includes(plan.status))
      .sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())[0]?.id ?? null;
  const currentProjectChats = [...(currentProject?.chats ?? [])].sort((a, b) => {
    if (a.isPinned && !b.isPinned) return -1;
    if (!a.isPinned && b.isPinned) return 1;
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  });

  if (projectsLoading && !projects.length) {
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
            onCancel={handleCancelMessage}
            projects={projects}
            activeChatId={activeChatId}
            activePlanId={activePlanId}
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
            verificationIssues={chat.verificationIssues}
            observationStatus={chat.observationStatus}
            observation={chat.observation}
            observations={chat.observations}
            showObservationsInChat={showObservationsInChat}
            persistentError={chat.persistentError}
            onRetryPersistentError={handleRetryObservation}
            awaitingUserQuery={awaitingUserQuery}
            userQueriesByCheckpoint={userQueriesByCheckpoint}
            visionPreprocessing={chat.visionPreprocessing}
          />
        }
        rightPanel={
          <ActionsPanel
            toolCalls={chat.toolCalls}
            isProcessing={isProcessing}
            subAgentRuns={chat.subAgentRuns}
            fileEdits={chat.fileEdits}
            checkpoints={chat.checkpoints}
            reasoningBlocks={chat.reasoningBlocks}
            todos={chat.todos}
            plans={chat.plans}
            streamingReasoningBlockIds={chat.streamingReasoningBlockIds}
            onRevertFile={handleRevertFile}
            onRevertCheckpoint={handleRevertToCheckpoint}
            onApproveCommand={handleApproveCommand}
            onRejectCommand={handleRejectCommand}
            onSavePlan={handleSavePlan}
            onApprovePlan={handleApprovePlan}
            onOpenImplementationChat={(chatId) => {
              void handleOpenImplementationChat(chatId);
            }}
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
        currentModelProvider={settings.currentModelProvider}
        currentModelKey={settings.currentModelKey}
        subAgentModel={settings.subAgentModel}
        subAgentModelKey={settings.subAgentModelKey}
        visionPreprocessorModel={settings.visionPreprocessorModel}
        visionPreprocessorModelKey={settings.visionPreprocessorModelKey}
        reasoningLevel={settings.reasoningLevel}
        setReasoningLevel={settings.setReasoningLevel}
        modelsByProvider={settings.modelsByProvider}
        modelMetadataByKey={settings.modelMetadataByKey}
        loading={settings.loading}
        changeModel={settings.changeModel}
        changeSubAgentModel={settings.changeSubAgentModel}
        changeVisionPreprocessorModel={settings.changeVisionPreprocessorModel}
      />
      <SettingsModal
        visible={settingsTab != null}
        onClose={() => setSettingsTab(null)}
        initialTab={settingsTab}
        activeChatId={activeChatId}
        onProviderModelsChanged={() => {
          void settings.refreshSettings();
        }}
      />
      <Modal
        visible={iterationLimitPause != null}
        onClose={() => setIterationLimitPause(null)}
        title="Iteration Limit Reached"
        subtitle={`Checkpoint ${iterationLimitPause?.checkpointId ?? ''}`}
        maxWidth="max-w-lg"
        footer={
          <div className="flex justify-end gap-2">
            <button
              type="button"
              className="px-3 py-2 text-sm rounded-lg border border-gray-600 text-gray-200 hover:bg-gray-700/40"
              onClick={() => setIterationLimitPause(null)}
            >
              Stop Here
            </button>
            <button
              type="button"
              className="px-3 py-2 text-sm rounded-lg bg-cyan-500 text-gray-950 font-medium hover:bg-cyan-400 disabled:opacity-60"
              onClick={handleContinuePausedRun}
              disabled={continuingPausedRun}
            >
              {continuingPausedRun ? 'Continuing…' : 'Continue'}
            </button>
          </div>
        }
      >
        <div className="px-6 py-5 space-y-2">
          <p className="text-sm text-gray-200">
            {iterationLimitPause?.message ??
              'The agent reached its iteration limit and paused. Continue from this checkpoint?'}
          </p>
          <p className="text-xs text-gray-400">
            Limit: {iterationLimitPause?.maxIterations ?? 0} iterations
            {iterationLimitPause?.iteration ? ` (reached ${iterationLimitPause.iteration})` : ''}
          </p>
        </div>
      </Modal>
    </div>
  );
}
