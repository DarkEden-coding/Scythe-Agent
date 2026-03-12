import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { ChatPanel } from './components/chat/ChatPanel';
import { ActionsPanel } from './components/ActionsPanel';
import { AppHeader } from './components/header/AppHeader';
import { ResizableLayout } from './components/layout/ResizableLayout';
import { EnhancedModelPicker } from './components/EnhancedModelPicker';
import { SettingsModal } from './components/SettingsModal';
import { Modal } from './components/Modal';
import { useToast } from './hooks/useToast';
import { useQuery } from './contexts/QueryContext';
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

interface QueuedMessagePayload {
  readonly content: string;
  readonly mode?: 'default' | 'planning' | 'plan_edit';
  readonly activePlanId?: string;
  readonly referencedFiles?: string[];
  readonly attachments?: { data: string; mimeType: string; name?: string }[];
}

interface QueuedMessageItem {
  readonly id: string;
  readonly chatId: string;
  readonly createdAt: string;
  readonly payload: QueuedMessagePayload;
}

type QueuedMessagesByChat = Record<string, QueuedMessageItem[]>;

export function App() {
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [settingsTab, setSettingsTab] = useState<SettingsTabId | null>(null);
  const [chatWidth, setChatWidth] = useState(33.33);
  const [showObservationsInChat, setShowObservationsInChat] = useState(false);
  const { showNotification, notificationMessage, showToast } = useToast();
  const query = useQuery();
  const [processingChats, setProcessingChats] = useState<Set<string>>(new Set());
  const [iterationLimitPause, setIterationLimitPause] = useState<IterationLimitPauseState | null>(null);
  const [continuingPausedRun, setContinuingPausedRun] = useState(false);
  const [continuingInterruptedRun, setContinuingInterruptedRun] = useState(false);
  const [backendConnected, setBackendConnected] = useState(false);
  const [backendConnectionChecked, setBackendConnectionChecked] = useState(false);
  const [pendingRunStartChats, setPendingRunStartChats] = useState<Set<string>>(new Set());
  const [queueFrozenChats, setQueueFrozenChats] = useState<Set<string>>(new Set());
  const [pendingPriorityQueuedMessage, setPendingPriorityQueuedMessage] = useState<QueuedMessageItem | null>(null);
  const [queueDrainLockChatId, setQueueDrainLockChatId] = useState<string | null>(null);
  const [queuedMessagesByChat, setQueuedMessagesByChat] = useState<QueuedMessagesByChat>(() => {
    try {
      const raw = localStorage.getItem('queuedMessagesByChat');
      if (!raw) return {};
      const parsed = JSON.parse(raw) as unknown;
      if (!parsed || typeof parsed !== 'object') return {};
      return parsed as QueuedMessagesByChat;
    } catch {
      return {};
    }
  });

  // ── API hooks ──────────────────────────────────────────────────
  const chat = useChatHistory(activeChatId);
  const isProcessing = activeChatId != null
    && (
      processingChats.has(activeChatId)
      || pendingRunStartChats.has(activeChatId)
      || (chat.runtimeState?.chatId === activeChatId && chat.runtimeState?.isRunning === true)
    );

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
  const canContinueInterruptedRun = useMemo(() => {
    if (activeChatId == null || isProcessing || continuingPausedRun || continuingInterruptedRun) return false;
    if (awaitingUserQuery != null || iterationLimitPause != null) return false;
    const lastMessage = chat.messages.at(-1);
    if (lastMessage?.role !== 'agent') return false;
    const lastMessageTimestamp = lastMessage.timestamp.getTime();
    const postMessageToolCalls = [...chat.toolCalls]
      .filter((toolCall) => toolCall.timestamp.getTime() >= lastMessageTimestamp)
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
    const lastToolAction = postMessageToolCalls[0];
    if (
      lastToolAction?.name === 'submit_task'
      && lastToolAction.status === 'completed'
      && String(lastToolAction.output ?? '').trim() === 'Task submitted.'
    ) {
      return false;
    }

    const lastParallelGroupId = lastToolAction?.parallelGroupId != null && lastToolAction.isParallel
      ? lastToolAction.parallelGroupId
      : undefined;
    const lastParallelGroupHasSubmitTask = Boolean(
      lastParallelGroupId && postMessageToolCalls.some(
        (toolCall) =>
          toolCall.parallelGroupId === lastParallelGroupId
          && toolCall.name === 'submit_task'
          && toolCall.status === 'completed'
          && String(toolCall.output ?? '').trim() === 'Task submitted.',
      ),
    );
    if (lastParallelGroupHasSubmitTask) {
      return false;
    }

    const hasIncompleteToolCall = chat.toolCalls.some((toolCall) => toolCall.status === 'pending' || toolCall.status === 'running');
    const hasRecoverablePersistentError = Boolean(
      chat.persistentError && chat.persistentError.source !== 'observer' && chat.persistentError.source !== 'reflector',
    );
    const latestPostMessageActivityTimestamp = Math.max(
      lastMessageTimestamp,
      ...chat.toolCalls.map((toolCall) => toolCall.timestamp.getTime()),
      ...chat.fileEdits.map((fileEdit) => fileEdit.timestamp.getTime()),
      ...chat.reasoningBlocks.map((reasoningBlock) => reasoningBlock.timestamp.getTime()),
      ...chat.subAgentRuns.map((subAgentRun) => subAgentRun.timestamp.getTime()),
      ...chat.checkpoints.map((checkpoint) => checkpoint.timestamp.getTime()),
    );
    const hasPostMessageActivity = latestPostMessageActivityTimestamp > lastMessageTimestamp;
    return hasIncompleteToolCall || hasRecoverablePersistentError || hasPostMessageActivity;
  }, [
    activeChatId,
    awaitingUserQuery,
    chat.checkpoints,
    chat.fileEdits,
    chat.messages,
    chat.persistentError,
    chat.reasoningBlocks,
    chat.subAgentRuns,
    chat.toolCalls,
    continuingInterruptedRun,
    continuingPausedRun,
    isProcessing,
    iterationLimitPause,
  ]);
  const projectsApi = useProjects();
  const { projects, loading: projectsLoading, projectMemoriesByProject } = projectsApi;
  const settings = useSettings();

  useEffect(() => {
    let cancelled = false;

    const pollBackendHealth = async () => {
      const result = await api.getBackendHealth();
      if (cancelled) return;

      setBackendConnected(result.ok && result.data?.status === 'ok');
      setBackendConnectionChecked(true);
    };

    void pollBackendHealth();
    const intervalId = window.setInterval(() => {
      void pollBackendHealth();
    }, 2000);

    const handleWindowFocus = () => {
      void pollBackendHealth();
    };

    window.addEventListener('focus', handleWindowFocus);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
      window.removeEventListener('focus', handleWindowFocus);
    };
  }, []);

  const showBackendConnectionOverlay = !backendConnected || !backendConnectionChecked;

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

  useEffect(() => {
    const onMemorySettingsUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ showObservationsInChat?: boolean }>).detail;
      if (typeof detail?.showObservationsInChat === 'boolean') {
        setShowObservationsInChat(detail.showObservationsInChat);
      }
    };

    window.addEventListener('memory-settings-updated', onMemorySettingsUpdated as EventListener);
    return () => {
      window.removeEventListener('memory-settings-updated', onMemorySettingsUpdated as EventListener);
    };
  }, []);

  // Persist active chat so it restores on refresh (never clear — bootstrap may run before projects load)
  useEffect(() => {
    if (activeChatId) localStorage.setItem('activeChatId', activeChatId);
  }, [activeChatId]);

  useEffect(() => {
    try {
      const serialized = JSON.stringify(queuedMessagesByChat);
      localStorage.setItem('queuedMessagesByChat', serialized);
    } catch {
      // Ignore persistence errors.
    }
  }, [queuedMessagesByChat]);

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
  const queuedMessagesByChatRef = useRef(queuedMessagesByChat);
  queuedMessagesByChatRef.current = queuedMessagesByChat;
  const pendingPriorityQueuedMessageRef = useRef<QueuedMessageItem | null>(pendingPriorityQueuedMessage);
  pendingPriorityQueuedMessageRef.current = pendingPriorityQueuedMessage;
  const cancellationReasonByChatRef = useRef<Record<string, 'manual' | 'priority'>>({});

  const removeProcessing = useCallback((chatIdToRemove: string) => {
    setProcessingChatsRef.current((prev) => {
      const next = new Set(prev);
      next.delete(chatIdToRemove);
      return next;
    });
  }, []);

  const markPendingRunStart = useCallback((chatIdToMark: string) => {
    setPendingRunStartChats((prev) => {
      if (prev.has(chatIdToMark)) return prev;
      return new Set(prev).add(chatIdToMark);
    });
  }, []);

  const clearPendingRunStart = useCallback((chatIdToClear: string) => {
    setPendingRunStartChats((prev) => {
      if (!prev.has(chatIdToClear)) return prev;
      const next = new Set(prev);
      next.delete(chatIdToClear);
      return next;
    });
  }, []);

  const enqueueMessage = useCallback(
    (chatId: string, payload: QueuedMessagePayload) => {
      setQueuedMessagesByChat((prev) => {
        const existing = prev[chatId] ?? [];
        const nextItem: QueuedMessageItem = {
          id: `${chatId}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
          chatId,
          createdAt: new Date().toISOString(),
          payload,
        };
        return {
          ...prev,
          [chatId]: [...existing, nextItem],
        };
      });
    },
    [],
  );

  const removeQueuedMessage = useCallback((chatId: string, queuedId: string) => {
    setQueuedMessagesByChat((prev) => {
      const existing = prev[chatId];
      if (!existing) return prev;
      const nextForChat = existing.filter((item) => item.id !== queuedId);
      if (nextForChat.length === existing.length) return prev;
      return {
        ...prev,
        [chatId]: nextForChat,
      };
    });
  }, []);

  useEffect(() => {
    const activeRuntimeState = chat.runtimeState;
    if (activeChatId == null || activeRuntimeState?.chatId !== activeChatId) return;
    if (activeRuntimeState.isRunning) {
      clearPendingRunStart(activeChatId);
      setProcessingChats((prev) => new Set(prev).add(activeChatId));
      if (queueDrainLockChatId === activeChatId) {
        setQueueDrainLockChatId(null);
      }
      return;
    }
    if (pendingRunStartChats.has(activeChatId)) return;
    removeProcessing(activeChatId);
  }, [activeChatId, chat.runtimeState, clearPendingRunStart, pendingRunStartChats, queueDrainLockChatId, removeProcessing]);

  const handleAgentEvent = useCallback(
    (event: AgentEvent) => {
      if (event.type === 'chat_title_updated') {
        projectsApi.refresh();
        return;
      }
      if (event.type === 'agent_started') {
        clearPendingRunStart(event.chatId);
        setProcessingChats((prev) => new Set(prev).add(event.chatId));
        if (queueDrainLockChatId === event.chatId) {
          setQueueDrainLockChatId(null);
        }
      }
      if (event.type === 'agent_done') {
        clearPendingRunStart(event.chatId);
        removeProcessing(event.chatId);
        const cancellationReason = cancellationReasonByChatRef.current[event.chatId];
        if (cancellationReason != null) {
          delete cancellationReasonByChatRef.current[event.chatId];
        } else {
          setQueueFrozenChats((prev) => {
            if (!prev.has(event.chatId)) return prev;
            const next = new Set(prev);
            next.delete(event.chatId);
            return next;
          });
        }
      }
      if (event.type === 'agent_paused') {
        clearPendingRunStart(event.chatId);
        removeProcessing(event.chatId);
        delete cancellationReasonByChatRef.current[event.chatId];
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
        clearPendingRunStart(event.chatId);
        removeProcessing(event.chatId);
        delete cancellationReasonByChatRef.current[event.chatId];
        if (event.chatId === activeChatId) {
          const payload = event.payload as { message?: string };
          showToast(`Error: ${payload.message ?? 'Unknown error'}`);
        }
      }
      if (event.chatId !== activeChatId) return;
      chat.processEvent(event);
    },
    [activeChatId, chat, clearPendingRunStart, projectsApi, queueDrainLockChatId, removeProcessing, showToast],
  );

  useAgentEvents([activeChatId, ...processingChats], handleAgentEvent);

  // ── Actions that go through the API ────────────────────────────

  const sendPayloadNow = useCallback(
    async (chatIdToProcess: string, payload: QueuedMessagePayload) => {
      markPendingRunStart(chatIdToProcess);
      setProcessingChats((prev) => new Set(prev).add(chatIdToProcess));

      const res = await chat.sendMessage(payload.content, {
        mode: payload.mode,
        activePlanId: payload.activePlanId,
        referencedFiles: payload.referencedFiles,
        attachments: payload.attachments,
      });
      if (!res.ok) {
        clearPendingRunStart(chatIdToProcess);
        showToast(`Error: ${res.error}`);
        setProcessingChats((prev) => {
          const next = new Set(prev);
          next.delete(chatIdToProcess);
          return next;
        });
      }

      return res;
    },
    [chat, clearPendingRunStart, markPendingRunStart, showToast],
  );

  const waitForChatIdle = useCallback(
    async (chatIdToWaitFor: string, timeoutMs = 10000) => {
      const startedAt = Date.now();
      while (Date.now() - startedAt < timeoutMs) {
        const runtimeRes = await chat.refreshRuntimeState(chatIdToWaitFor);
        if (runtimeRes.ok && !runtimeRes.runtime?.isRunning) {
          return true;
        }
        await new Promise<void>((resolve) => {
          globalThis.setTimeout(resolve, 200);
        });
      }
      return false;
    },
    [chat],
  );

  const waitForRunStart = useCallback(
    async (chatIdToWaitFor: string, checkpointId: string, timeoutMs = 10000) => {
      const startedAt = Date.now();
      while (Date.now() - startedAt < timeoutMs) {
        const runtimeRes = await chat.refreshRuntimeState(chatIdToWaitFor);
        if (
          runtimeRes.ok
          && runtimeRes.runtime?.isRunning
          && runtimeRes.runtime.checkpointId === checkpointId
        ) {
          return true;
        }
        await new Promise<void>((resolve) => {
          globalThis.setTimeout(resolve, 200);
        });
      }
      return false;
    },
    [chat],
  );

  const handleSendMessage = async (
    content: string,
    options?: {
      mode?: 'default' | 'planning' | 'plan_edit';
      activePlanId?: string;
      referencedFiles?: string[];
      attachments?: { data: string; mimeType: string; name?: string }[];
    },
  ) => {
    if (activeChatId == null) return;
    const chatIdToProcess = activeChatId;
    const isChatBusy = isProcessing;
    const payload: QueuedMessagePayload = {
      content,
      mode: options?.mode,
      activePlanId: options?.activePlanId,
      referencedFiles: options?.referencedFiles,
      attachments: options?.attachments,
    };

    if (isChatBusy) {
      enqueueMessage(chatIdToProcess, payload);
      return;
    }

    await sendPayloadNow(chatIdToProcess, payload);
  };

  const handleCancelMessage = useCallback(() => {
    if (activeChatId == null) return;
    cancellationReasonByChatRef.current[activeChatId] = 'manual';
    setQueueFrozenChats((prev) => new Set(prev).add(activeChatId));
    if (pendingPriorityQueuedMessage?.chatId === activeChatId) {
      setQueuedMessagesByChat((prev) => ({
        ...prev,
        [activeChatId]: [pendingPriorityQueuedMessage, ...(prev[activeChatId] ?? [])],
      }));
      setPendingPriorityQueuedMessage(null);
    }
    if (queueDrainLockChatId === activeChatId) {
      setQueueDrainLockChatId(null);
    }
    clearPendingRunStart(activeChatId);
    void chat.cancelProcessing(activeChatId);
  }, [activeChatId, chat, clearPendingRunStart, pendingPriorityQueuedMessage, queueDrainLockChatId]);

  const handleDeleteQueuedMessage = useCallback(
    (queuedId: string) => {
      if (activeChatId == null) return;
      removeQueuedMessage(activeChatId, queuedId);
    },
    [activeChatId, removeQueuedMessage],
  );

  const handleSendQueuedNow = useCallback(
    async (queuedId: string) => {
      if (activeChatId == null) return;
      const chatId = activeChatId;
      const queuedForChat = queuedMessagesByChat[chatId] ?? [];
      const target = queuedForChat.find((item) => item.id === queuedId);
      if (!target) return;

      setPendingPriorityQueuedMessage(target);
      setQueueDrainLockChatId(chatId);
      removeQueuedMessage(chatId, queuedId);

      const hadActiveRun = isProcessing;
      if (hadActiveRun) {
        cancellationReasonByChatRef.current[chatId] = 'priority';
        clearPendingRunStart(chatId);
        const cancelRes = await chat.cancelProcessing(chatId);
        if (!cancelRes.ok) {
          delete cancellationReasonByChatRef.current[chatId];
          setPendingPriorityQueuedMessage(null);
          setQueueDrainLockChatId(null);
          setQueuedMessagesByChat((prev) => ({
            ...prev,
            [chatId]: [target, ...(prev[chatId] ?? [])],
          }));
          showToast(`Error: ${cancelRes.error}`);
          return;
        }

        const idleConfirmed = await waitForChatIdle(chatId);
        if (!idleConfirmed) {
          delete cancellationReasonByChatRef.current[chatId];
          if (pendingPriorityQueuedMessageRef.current?.id === target.id) {
            setPendingPriorityQueuedMessage(null);
            setQueueDrainLockChatId(null);
            setQueuedMessagesByChat((prev) => ({
              ...prev,
              [chatId]: [target, ...(prev[chatId] ?? [])],
            }));
          }
          showToast('Timed out waiting for the previous run to stop.');
          return;
        }
      }

      if (pendingPriorityQueuedMessageRef.current?.id !== target.id) {
        return;
      }

      const sendRes = await sendPayloadNow(chatId, target.payload);
      if (pendingPriorityQueuedMessageRef.current?.id !== target.id) {
        return;
      }

      if (!sendRes.ok) {
        setPendingPriorityQueuedMessage(null);
        setQueueDrainLockChatId(null);
        setQueuedMessagesByChat((prev) => ({
          ...prev,
          [chatId]: [target, ...(prev[chatId] ?? [])],
        }));
        return;
      }

      const checkpointId = sendRes.data.checkpoint?.id;
      if (!checkpointId) {
        setPendingPriorityQueuedMessage(null);
        setQueueDrainLockChatId(null);
        showToast('Message was sent, but the new run checkpoint was missing.');
        return;
      }

      const runStarted = await waitForRunStart(chatId, checkpointId);
      if (pendingPriorityQueuedMessageRef.current?.id !== target.id) {
        return;
      }

      setPendingPriorityQueuedMessage(null);
      setQueueDrainLockChatId(null);
      if (!runStarted) {
        showToast('Message was sent, but the new agent run was not confirmed within 10 seconds.');
      }
    },
    [
      activeChatId,
      chat,
      clearPendingRunStart,
      isProcessing,
      queuedMessagesByChat,
      removeQueuedMessage,
      sendPayloadNow,
      showToast,
      waitForChatIdle,
      waitForRunStart,
    ],
  );

  useEffect(() => {
    if (
      activeChatId == null
      || isProcessing
      || awaitingUserQuery != null
      || pendingPriorityQueuedMessage != null
      || queueFrozenChats.has(activeChatId)
      || queueDrainLockChatId === activeChatId
    ) {
      return;
    }
    const nextQueued = queuedMessagesByChatRef.current[activeChatId]?.[0];
    if (!nextQueued) return;

    removeQueuedMessage(activeChatId, nextQueued.id);
    void sendPayloadNow(activeChatId, nextQueued.payload).then((res) => {
      if (!res.ok) {
        setQueuedMessagesByChat((prev) => ({
          ...prev,
          [activeChatId]: [nextQueued, ...(prev[activeChatId] ?? [])],
        }));
      }
    });
  }, [
    activeChatId,
    awaitingUserQuery,
    isProcessing,
    pendingPriorityQueuedMessage,
    queueFrozenChats,
    queueDrainLockChatId,
    removeQueuedMessage,
    sendPayloadNow,
  ]);

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

  const handleContinueInterruptedRun = useCallback(async () => {
    if (activeChatId == null) return;
    setContinuingInterruptedRun(true);
    setProcessingChats((prev) => new Set(prev).add(activeChatId));
    const res = await chat.continueAgent();
    if (res.ok) {
      showToast('Continuing agent run');
    } else {
      showToast(`Error: ${res.error}`);
      setProcessingChats((prev) => {
        const next = new Set(prev);
        next.delete(activeChatId);
        return next;
      });
    }
    setContinuingInterruptedRun(false);
  }, [activeChatId, chat, showToast]);

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

  const handleEditMessage = async (messageId: string, newContent: string, referencedFiles?: string[]) => {
    if (!(await query.confirm('This will revert all changes after this message and re-run the agent with the new content. Continue?'))) {
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
        return { ok: false as const, error: res.error };
      }
      if (res.data.conflict) {
        showToast('Plan conflict detected. Refresh and retry.');
      } else {
        showToast('Plan updated');
      }
      return {
        ok: true as const,
        data: {
          conflict: res.data.conflict,
          plan: res.data.plan,
        },
      };
    },
    [chat, showToast],
  );

  const handleApprovePlan = useCallback(
    async (planId: string, action: 'keep_context' | 'clear_context') => {
      const res = await chat.approvePlan(planId, action);
      if (!res.ok) {
        showToast(`Error: ${res.error}`);
        return { ok: false as const, error: res.error };
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
      return {
        ok: true as const,
        data: {
          plan: res.data.plan,
          implementationChatId,
        },
      };
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

  const handleLoadProjectMemories = async (projectId: string, options?: { force?: boolean }) => {
    const res = await projectsApi.getProjectMemories(projectId, options);
    if (!res.ok) showToast(`Error: ${res.error}`);
    return res;
  };

  const handleUpsertProjectMemory = async (
    projectId: string,
    payload: { title: string; contentMarkdown: string },
  ) => {
    const res = await projectsApi.upsertProjectMemory(projectId, payload);
    if (res.ok) {
      showToast('Project memory saved');
    } else {
      showToast(`Error: ${res.error}`);
    }
    return res;
  };

  const handleDeleteProjectMemory = async (projectId: string, title: string) => {
    const res = await projectsApi.deleteProjectMemory(projectId, title);
    if (res.ok) {
      showToast('Project memory deleted');
    } else {
      showToast(`Error: ${res.error}`);
    }
    return res;
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
        className={showBackendConnectionOverlay ? 'pointer-events-none opacity-60' : undefined}
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
            projectMemoriesByProject={projectMemoriesByProject}
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
            onLoadProjectMemories={handleLoadProjectMemories}
            onUpsertProjectMemory={handleUpsertProjectMemory}
            onDeleteProjectMemory={handleDeleteProjectMemory}
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
            canContinueInterruptedRun={canContinueInterruptedRun}
            onContinueInterruptedRun={handleContinueInterruptedRun}
            continueBusy={continuingInterruptedRun}
            queuedMessages={
              activeChatId ? (queuedMessagesByChat[activeChatId] ?? []).map((item) => ({
                id: item.id,
                createdAt: item.createdAt,
                payload: item.payload,
              })) : []
            }
            onDeleteQueuedMessage={handleDeleteQueuedMessage}
            onSendQueuedNow={handleSendQueuedNow}
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

      {showBackendConnectionOverlay && (
        <div className="absolute inset-0 z-40 flex items-center justify-center bg-gray-950/88 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-4 rounded-2xl border border-gray-800 bg-gray-900/90 px-8 py-7 shadow-2xl shadow-black/40">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-cyan-500/20 border-t-cyan-400" />
            <div className="text-center">
              <p className="text-sm font-medium text-gray-100">
                {backendConnectionChecked ? 'Waiting for backend connection…' : 'Connecting to backend…'}
              </p>
              <p className="mt-1 text-xs text-gray-400">
                The interface will unlock automatically when the backend responds.
              </p>
            </div>
          </div>
        </div>
      )}

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
