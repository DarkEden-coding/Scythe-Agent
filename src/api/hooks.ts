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

/**
 * Fetches the complete chat history for a given chatId and provides
 * mutable state + action dispatchers for the full agent session.
 */
export function useChatHistory(chatId: string, client: ApiClient = defaultApi) {
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

  // Fetch on mount / chatId change
  useEffect(() => {
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
    async (projectId: string, title: string) => {
      const res = await client.createChat({ projectId, title });
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

/* ── useSettings ────────────────────────────────────────────────── */

export function useSettings(client: ApiClient = defaultApi) {
  const [state, run] = useAsyncState<GetSettingsResponse>();
  const [currentModel, setCurrentModel] = useState('Claude Sonnet 4');
  const [autoApproveRules, setAutoApproveRules] = useState<AutoApproveRule[]>([]);

  useEffect(() => {
    run(client.getSettings()).then((res) => {
      if (res.ok) {
        setCurrentModel(res.data.model);
        setAutoApproveRules(res.data.autoApproveRules);
      }
    });
  }, [client, run]);

  const changeModel = useCallback(
    async (model: string) => {
      const res = await client.changeModel({ model });
      if (res.ok) {
        setCurrentModel(res.data.model);
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
    contextLimit: state.data?.contextLimit ?? 128_000,
    autoApproveRules,
    changeModel,
    updateAutoApproveRules,
    getAutoApproveRules,
  };
}

/* ── useAgentEvents ─────────────────────────────────────────────── */

/**
 * Subscribes to the real-time agent event stream for a given chat.
 * Calls `onEvent` for each received event.
 */
export function useAgentEvents(
  chatId: string,
  onEvent: (event: AgentEvent) => void,
  client: ApiClient = defaultApi,
) {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    const unsubscribe = client.subscribeToAgentEvents(chatId, (event) => {
      onEventRef.current(event);
    });
    return unsubscribe;
  }, [chatId, client]);
}

/* ── Re-exports for convenience ─────────────────────────────────── */

export { api as defaultApiClient } from './client';
export type { ApiClient } from './client';
