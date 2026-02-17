/**
 * React hooks that wrap the ApiClient for use in components.
 *
 * These hooks handle loading/error state, caching, and real-time event
 * subscriptions. They use the singleton `api` instance by default but
 * accept an optional override for testing.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { api as defaultApi, ApiClient } from './client';
import type {
  ApiResponse,
  GetProjectsResponse,
  GetSettingsResponse,
  AgentEvent,
  AutoApproveRule,
  GetFsChildrenResponse,
  OpenRouterConfig,
  SetApiKeyResponse,
  TestConnectionResponse,
  SyncModelsResponse,
} from './types';
import type {
  Message,
  ToolCall,
  FileEdit,
  Checkpoint,
  ContextItem,
  ReasoningBlock,
} from '../types';

/* ── API -> UI normalization helpers ─────────────────────────────── */

const toDate = (value: Date | string): Date =>
  value instanceof Date ? value : new Date(value);

const normalizeMessage = (m: Message): Message => ({
  ...m,
  timestamp: toDate(m.timestamp),
});

const normalizeToolCall = (tc: ToolCall): ToolCall => ({
  ...tc,
  timestamp: toDate(tc.timestamp),
});

const normalizeFileEdit = (fe: FileEdit): FileEdit => ({
  ...fe,
  timestamp: toDate(fe.timestamp),
});

const normalizeCheckpoint = (cp: Checkpoint): Checkpoint => ({
  ...cp,
  timestamp: toDate(cp.timestamp),
});

const normalizeReasoningBlock = (rb: ReasoningBlock): ReasoningBlock => ({
  ...rb,
  timestamp: toDate(rb.timestamp),
});

const upsertById = <T extends { id: string }>(items: T[], next: T): T[] => {
  const idx = items.findIndex((item) => item.id === next.id);
  if (idx === -1) return [...items, next];
  const copy = [...items];
  copy[idx] = next;
  return copy;
};

const uniqueById = <T extends { id: string }>(items: T[]): T[] =>
  items.filter((item, idx, all) => all.findIndex((candidate) => candidate.id === item.id) === idx);

/* ── Generic async state ────────────────────────────────────────── */

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

function useAsyncState<T>(initial: T | null = null): [AsyncState<T>, (p: Promise<ApiResponse<T>>) => Promise<ApiResponse<T>>] {
  const [state, setState] = useState<AsyncState<T>>({
    data: initial,
    loading: false,
    error: null,
  });

  const run = useCallback(async (promise: Promise<ApiResponse<T>>) => {
    setState((s) => ({ ...s, loading: true, error: null }));
    const result = await promise;
    if (result.ok) {
      setState({ data: result.data, loading: false, error: null });
    } else {
      setState((s) => ({ ...s, loading: false, error: result.error ?? 'Unknown error' }));
    }
    return result;
  }, []);

  return [state, run];
}

/* ── useChatHistory ─────────────────────────────────────────────── */

const isValidChatId = (id: string | null | undefined): id is string =>
  typeof id === 'string' && id.length > 0;

/**
 * Fetches the complete chat history for a given chatId and provides
 * mutable state + action dispatchers for the full agent session.
 */
export function useChatHistory(chatId: string | null | undefined, client: ApiClient = defaultApi) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [fileEdits, setFileEdits] = useState<FileEdit[]>([]);
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [reasoningBlocks, setReasoningBlocks] = useState<ReasoningBlock[]>([]);
  const [contextItems, setContextItems] = useState<ContextItem[]>([]);
  const [maxTokens, setMaxTokens] = useState(128_000);
  const [model, setModel] = useState('Claude Sonnet 4');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processingChats, setProcessingChats] = useState<Set<string>>(new Set());

  // Fetch on mount / chatId change — skip when chatId is invalid
  useEffect(() => {
    if (!isValidChatId(chatId)) {
      setLoading(false);
      setMessages([]);
      setToolCalls([]);
      setFileEdits([]);
      setCheckpoints([]);
      setReasoningBlocks([]);
      setContextItems([]);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);

    client.getChatHistory(chatId).then((res) => {
      if (cancelled) return;
      if (res.ok) {
        const d = res.data;
        setMessages(uniqueById(d.messages.map(normalizeMessage)));
        setToolCalls(uniqueById(d.toolCalls.map(normalizeToolCall)));
        setFileEdits(uniqueById(d.fileEdits.map(normalizeFileEdit)));
        setCheckpoints(uniqueById(d.checkpoints.map(normalizeCheckpoint)));
        setReasoningBlocks(uniqueById(d.reasoningBlocks.map(normalizeReasoningBlock)));
        setContextItems(d.contextItems);
        setMaxTokens(d.maxTokens);
        setModel(d.model);
        setError(null);
      } else {
        setError(res.error ?? 'Failed to load chat history');
      }
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [chatId, client]);

  /* ── Action: send message ──────────────────────────────────── */
  const sendMessage = useCallback(
    async (content: string) => {
      if (!isValidChatId(chatId)) {
        return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
      }
      setProcessingChats((prev) => new Set(prev).add(chatId));
      try {
        const res = await client.sendMessage({ chatId, content });
        if (res.ok) {
          const nextMessage = normalizeMessage(res.data.message);
          setMessages((prev) => upsertById(prev, nextMessage));
          if (res.data.checkpoint) {
            const nextCheckpoint = normalizeCheckpoint(res.data.checkpoint);
            setCheckpoints((prev) => upsertById(prev, nextCheckpoint));
          }
        }
        return res;
      } finally {
        setProcessingChats((prev) => {
          const next = new Set(prev);
          next.delete(chatId);
          return next;
        });
      }
    },
    [chatId, client],
  );

  /** Check if any specific chat is currently processing. */
  const isChatProcessing = useCallback(
    (targetChatId?: string) => processingChats.has(targetChatId ?? chatId),
    [processingChats, chatId],
  );

  /** Get all currently processing chat IDs. */
  const getProcessingChats = useCallback(
    () => Array.from(processingChats),
    [processingChats],
  );

  /** Cancel processing for a specific chat. */
  const cancelProcessing = useCallback(
    (targetChatId?: string) => {
      const id = targetChatId ?? chatId;
      client.cancelSession(id);
      setProcessingChats((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    },
    [chatId, client],
  );

  /* ── Action: approve command ───────────────────────────────── */
  const approveCommand = useCallback(
    async (toolCallId: string) => {
      const res = await client.approveCommand({ chatId, toolCallId });
      if (res.ok) {
        setToolCalls((prev) =>
          prev.map((tc) => (tc.id === toolCallId ? normalizeToolCall(res.data.toolCall) : tc)),
        );
        if (res.data.fileEdits.length) {
          setFileEdits((prev) => [...prev, ...res.data.fileEdits.map(normalizeFileEdit)]);
        }
      }
      return res;
    },
    [chatId, client],
  );

  /* ── Action: reject command ────────────────────────────────── */
  const rejectCommand = useCallback(
    async (toolCallId: string, reason?: string) => {
      const res = await client.rejectCommand({ chatId, toolCallId, reason });
      if (res.ok) {
        setToolCalls((prev) =>
          prev.map((tc) =>
            tc.id === toolCallId ? { ...tc, status: 'error' as const } : tc,
          ),
        );
      }
      return res;
    },
    [chatId, client],
  );

  /* ── Action: summarize context ─────────────────────────────── */
  const summarizeContext = useCallback(async () => {
    const res = await client.summarizeContext({ chatId });
    if (res.ok) {
      setContextItems(res.data.contextItems);
    }
    return res;
  }, [chatId, client]);

  /* ── Action: remove context item (local only) ──────────────── */
  const removeContextItem = useCallback((itemId: string) => {
    setContextItems((prev) => prev.filter((i) => i.id !== itemId));
  }, []);

  /* ── Action: revert to checkpoint ──────────────────────────── */
  const revertToCheckpoint = useCallback(
    async (checkpointId: string) => {
      const res = await client.revertToCheckpoint({ chatId, checkpointId });
      if (res.ok) {
        setMessages(uniqueById(res.data.messages.map(normalizeMessage)));
        setToolCalls(uniqueById(res.data.toolCalls.map(normalizeToolCall)));
        setFileEdits(uniqueById(res.data.fileEdits.map(normalizeFileEdit)));
        setCheckpoints(uniqueById(res.data.checkpoints.map(normalizeCheckpoint)));
        setReasoningBlocks(uniqueById(res.data.reasoningBlocks.map(normalizeReasoningBlock)));
      }
      return res;
    },
    [chatId, client],
  );

  /* ── Action: revert file ───────────────────────────────────── */
  const revertFile = useCallback(
    async (fileEditId: string) => {
      const res = await client.revertFile({ chatId, fileEditId });
      if (res.ok) {
        setFileEdits(uniqueById(res.data.fileEdits.map(normalizeFileEdit)));
      }
      return res;
    },
    [chatId, client],
  );

  return {
    // State
    messages,
    toolCalls,
    fileEdits,
    checkpoints,
    reasoningBlocks,
    contextItems,
    maxTokens,
    model,
    loading,
    error,
    // Actions
    sendMessage,
    approveCommand,
    rejectCommand,
    summarizeContext,
    removeContextItem,
    revertToCheckpoint,
    revertFile,
    // Concurrent processing
    isChatProcessing,
    getProcessingChats,
    cancelProcessing,
    // Setters for direct manipulation
    setMessages,
    setToolCalls,
    setFileEdits,
    setCheckpoints,
    setReasoningBlocks,
    setContextItems,
    setModel,
    setMaxTokens,
  };
}

/* ── useProjects ────────────────────────────────────────────────── */

export function useProjects(client: ApiClient = defaultApi) {
  const [state, run] = useAsyncState<GetProjectsResponse>({ projects: [] });
  const [projects, setProjects] = useState<GetProjectsResponse['projects']>([]);

  useEffect(() => {
    run(client.getProjects()).then((res) => {
      if (res.ok) {
        setProjects(res.data.projects);
      }
    });
  }, [client, run]);

  const normalizedProjects = (projects ?? []).map((project) => ({
    ...project,
    lastAccessed: toDate(project.lastAccessed),
    chats: project.chats.map((chat) => ({
      ...chat,
      timestamp: toDate(chat.timestamp),
    })),
  }));

  const refresh = useCallback(async () => {
    const res = await run(client.getProjects());
    if (res.ok) {
      setProjects(res.data.projects);
    }
    return res;
  }, [client, run]);

  const createProject = useCallback(
    async (name: string, path: string) => {
      const res = await client.createProject({ name, path });
      if (res.ok) {
        await refresh();
      }
      return res;
    },
    [client, refresh],
  );

  const createChat = useCallback(
    async (projectId: string, title?: string) => {
      const res = await client.createChat({ projectId, title: title?.trim() || undefined });
      if (res.ok) {
        await refresh();
      }
      return res;
    },
    [client, refresh],
  );

  const renameProject = useCallback(
    async (projectId: string, name: string) => {
      const res = await client.updateProject(projectId, { name });
      if (res.ok) {
        await refresh();
      }
      return res;
    },
    [client, refresh],
  );

  const renameChat = useCallback(
    async (chatId: string, title: string) => {
      const res = await client.updateChat({ chatId, title });
      if (res.ok) {
        await refresh();
      }
      return res;
    },
    [client, refresh],
  );

  const pinChat = useCallback(
    async (chatId: string, isPinned: boolean) => {
      const res = await client.updateChat({ chatId, isPinned });
      if (res.ok) {
        await refresh();
      }
      return res;
    },
    [client, refresh],
  );

  const deleteProject = useCallback(
    async (projectId: string) => {
      const res = await client.deleteProject(projectId);
      if (res.ok) {
        await refresh();
      }
      return res;
    },
    [client, refresh],
  );

  const deleteChat = useCallback(
    async (chatId: string) => {
      const res = await client.deleteChat({ chatId });
      if (res.ok) {
        await refresh();
      }
      return res;
    },
    [client, refresh],
  );

  const reorderProjects = useCallback(
    async (projectIds: string[]) => {
      const res = await client.reorderProjects({ projectIds });
      if (res.ok) {
        setProjects(res.data.projects);
      }
      return res;
    },
    [client],
  );

  const reorderChats = useCallback(
    async (projectId: string, chatIds: string[]) => {
      const res = await client.reorderChats({ projectId, chatIds });
      if (res.ok) {
        setProjects(res.data.projects);
      }
      return res;
    },
    [client],
  );

  return {
    projects: normalizedProjects,
    loading: state.loading,
    error: state.error,
    refresh,
    createProject,
    createChat,
    renameProject,
    renameChat,
    pinChat,
    deleteProject,
    deleteChat,
    reorderProjects,
    reorderChats,
  };
}

/* ── useFilesystemBrowser ──────────────────────────────────────── */

export function useFilesystemBrowser(initialPath?: string, client: ApiClient = defaultApi) {
  const [state, run] = useAsyncState<GetFsChildrenResponse>();
  const [path, setPath] = useState(initialPath ?? '');
  const [allowedRoots, setAllowedRoots] = useState<string[]>([]);

  const load = useCallback(
    async (nextPath?: string) => {
      const target = nextPath ?? path;
      const res = await run(client.getFsChildren(target || undefined));
      if (res.ok) {
        setPath(res.data.path);
        setAllowedRoots(res.data.allowedRoots);
      }
      return res;
    },
    [client, path, run],
  );

  useEffect(() => {
    load(initialPath);
  }, [initialPath, load]);

  return {
    data: state.data,
    loading: state.loading,
    error: state.error,
    path,
    allowedRoots,
    load,
    setPath,
  };
}

/* ── Settings cache (TTL 5 min, reduces bandwidth, enables instant display) ── */

const SETTINGS_CACHE_TTL_MS = 5 * 60 * 1000;
let settingsCache: { data: GetSettingsResponse; fetchedAt: number } | null = null;

async function getSettingsCached(
  client: ApiClient,
): Promise<ApiResponse<GetSettingsResponse>> {
  const now = Date.now();
  if (
    settingsCache &&
    now - settingsCache.fetchedAt < SETTINGS_CACHE_TTL_MS
  ) {
    return { ok: true, data: settingsCache.data };
  }
  const res = await client.getSettings();
  if (res.ok) {
    settingsCache = { data: res.data, fetchedAt: Date.now() };
  }
  return res;
}

function getSettingsCacheSnapshot(): GetSettingsResponse | null {
  if (
    settingsCache &&
    Date.now() - settingsCache.fetchedAt < SETTINGS_CACHE_TTL_MS
  ) {
    return settingsCache.data;
  }
  return null;
}

/* ── useSettings ────────────────────────────────────────────────── */

export function useSettings(client: ApiClient = defaultApi) {
  const cached = getSettingsCacheSnapshot();
  const [state, setState] = useState<{
    data: GetSettingsResponse | null;
    loading: boolean;
    error: string | null;
  }>({
    data: cached,
    loading: !cached,
    error: null,
  });
  const [currentModel, setCurrentModel] = useState(
    cached?.model ?? 'Claude Sonnet 4',
  );
  const [autoApproveRules, setAutoApproveRules] = useState<AutoApproveRule[]>(
    cached?.autoApproveRules ?? [],
  );

  const fetchSettings = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    const res = await getSettingsCached(client);
    if (res.ok) {
      setState({ data: res.data, loading: false, error: null });
      setCurrentModel(res.data.model);
      setAutoApproveRules(res.data.autoApproveRules);
    } else {
      setState((s) => ({
        ...s,
        loading: false,
        error: res.error ?? 'Unknown error',
      }));
    }
    return res;
  }, [client]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const prefetchSettings = useCallback(() => {
    return getSettingsCached(client).then((res) => {
      if (res.ok) {
        setState({ data: res.data, loading: false, error: null });
        setCurrentModel(res.data.model);
        setAutoApproveRules(res.data.autoApproveRules);
      }
      return res;
    });
  }, [client]);

  const changeModel = useCallback(
    async (model: string) => {
      const res = await client.changeModel({ model });
      if (res.ok) {
        setCurrentModel(res.data.model);
        if (settingsCache) {
          settingsCache = { ...settingsCache, data: { ...settingsCache.data, model: res.data.model } };
        }
      }
      return res;
    },
    [client],
  );

  const updateAutoApproveRules = useCallback(
    async (rules: Omit<AutoApproveRule, 'id' | 'createdAt'>[]) => {
      const res = await client.setAutoApproveRules({ rules });
      if (res.ok) {
        setAutoApproveRules(res.data.rules);
      }
      return res;
    },
    [client],
  );

  const getAutoApproveRules = useCallback(async () => {
    const res = await client.getAutoApproveRules();
    if (res.ok) {
      setAutoApproveRules(res.data.rules);
    }
    return res;
  }, [client]);

  return {
    settings: state.data,
    loading: state.loading,
    error: state.error,
    currentModel,
    availableModels: state.data?.availableModels ?? [],
    modelsByProvider: state.data?.modelsByProvider ?? {},
    modelMetadata: state.data?.modelMetadata ?? {},
    contextLimit: state.data?.contextLimit ?? 128_000,
    autoApproveRules,
    changeModel,
    updateAutoApproveRules,
    getAutoApproveRules,
    prefetchSettings,
  };
}

/* ── useOpenRouter ──────────────────────────────────────────────── */

/**
 * Hook for managing OpenRouter configuration.
 * Provides state and methods for API key management, connection testing,
 * and model syncing.
 */
export function useOpenRouter(client: ApiClient = defaultApi) {
  const [config, setConfig] = useState<OpenRouterConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await client.getOpenRouterConfig();
    if (res.ok) {
      setConfig(res.data);
    } else {
      setError(res.error ?? 'Failed to load OpenRouter config');
    }
    setLoading(false);
    return res;
  }, [client]);

  useEffect(() => {
    refreshConfig();
  }, [refreshConfig]);

  const setApiKey = useCallback(
    async (apiKey: string): Promise<ApiResponse<SetApiKeyResponse>> => {
      setLoading(true);
      setError(null);
      const res = await client.setOpenRouterApiKey({ apiKey });
      if (res.ok) {
        await refreshConfig();
      } else {
        setError(res.error ?? 'Failed to set API key');
      }
      setLoading(false);
      return res;
    },
    [client, refreshConfig],
  );

  const testConnection = useCallback(async (): Promise<ApiResponse<TestConnectionResponse>> => {
    setTesting(true);
    setError(null);
    const res = await client.testOpenRouterConnection();
    if (!res.ok) {
      setError(res.error ?? 'Connection test failed');
    }
    setTesting(false);
    return res;
  }, [client]);

  const syncModels = useCallback(async (): Promise<ApiResponse<SyncModelsResponse>> => {
    setSyncing(true);
    setError(null);
    const res = await client.syncOpenRouterModels();
    if (res.ok) {
      await refreshConfig();
    } else {
      setError(res.error ?? 'Model sync failed');
    }
    setSyncing(false);
    return res;
  }, [client, refreshConfig]);

  return {
    config,
    loading,
    testing,
    syncing,
    error,
    setApiKey,
    testConnection,
    syncModels,
    refreshConfig,
  };
}

/* ── useAgentEvents ─────────────────────────────────────────────── */

/**
 * Subscribes to the real-time agent event stream for a given chat.
 * Calls `onEvent` for each received event.
 * Skips subscription when chatId is invalid.
 */
export function useAgentEvents(
  chatId: string | null | undefined,
  onEvent: (event: AgentEvent) => void,
  client: ApiClient = defaultApi,
) {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!isValidChatId(chatId)) return () => {};
    const unsubscribe = client.subscribeToAgentEvents(chatId, (event) => {
      onEventRef.current(event);
    });
    return unsubscribe;
  }, [chatId, client]);
}

/* ── Re-exports for convenience ─────────────────────────────────── */

export { api as defaultApiClient } from './client';
export type { ApiClient } from './client';
