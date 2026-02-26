/**
 * Fetches the complete chat history for a given chatId and provides
 * mutable state + action dispatchers for the full agent session.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { api as defaultApi, ApiClient } from '@/api/client';
import {
  normalizeMessage,
  normalizeToolCall,
  normalizeFileEdit,
  normalizeCheckpoint,
  normalizeReasoningBlock,
  normalizeSubAgentRun,
  normalizeTodo,
  normalizePlan,
  upsertById,
  uniqueById,
  isValidChatId,
} from '@/api/normalizers';
import type {
  Message,
  SubAgentRun,
  ToolCall,
  FileEdit,
  Checkpoint,
  ContextItem,
  ReasoningBlock,
  TodoItem,
  ProjectPlan,
  ObservationData,
  VerificationIssues,
} from '@/types';
import type {
  AgentErrorPayload,
  AgentEvent,
  AgentObservationStatusPayload,
  AgentPlanConflictPayload,
  AgentPlanPayload,
  ChatMemoryStateResponse,
} from '@/api/types';
import type { ObservationStatus } from '@/components/chat/ObservationStatusIndicator';

interface ChatPersistentError {
  message: string;
  source?: string;
  retryable?: boolean;
  retryAction?: string;
}

function toObservationData(memory: ChatMemoryStateResponse): ObservationData | null {
  if (!memory.hasMemoryState || memory.strategy !== 'observational') return null;

  const state = memory.state ?? {};
  const generation =
    typeof state.generation === 'number' ? state.generation : undefined;
  const tokenCount =
    typeof state.tokenCount === 'number' ? state.tokenCount : undefined;
  const latestStored = memory.observations?.[0];
  const triggerTokenCount =
    typeof state.triggerTokenCount === 'number'
      ? state.triggerTokenCount
      : typeof latestStored?.triggerTokenCount === 'number'
        ? latestStored.triggerTokenCount
        : undefined;
  const observedUpToMessageId =
    typeof state.observedUpToMessageId === 'string' ? state.observedUpToMessageId : undefined;
  const currentTask =
    typeof state.currentTask === 'string' ? state.currentTask : undefined;
  const suggestedResponse =
    typeof state.suggestedResponse === 'string' ? state.suggestedResponse : undefined;
  const content = typeof state.content === 'string' ? state.content : undefined;
  const timestamp =
    typeof state.timestamp === 'string'
      ? state.timestamp
      : typeof memory.updatedAt === 'string'
        ? memory.updatedAt
        : undefined;

  return {
    id: typeof state.timestamp === 'string' ? `state-${state.timestamp}` : undefined,
    hasObservations: true,
    generation,
    tokenCount,
    triggerTokenCount,
    observedUpToMessageId,
    currentTask,
    suggestedResponse,
    content,
    timestamp,
    source: 'stored',
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null;
}

function toMemorySnapshotSignature(memory: ChatMemoryStateResponse | null | undefined): string {
  if (!memory?.hasMemoryState) return 'none';

  const state = asRecord(memory.state);
  const latestStored = memory.observations?.[0];
  const buffer = asRecord(state?.buffer);
  const bufferChunks = Array.isArray(buffer?.chunks) ? buffer.chunks : [];
  const latestBufferChunk = asRecord(bufferChunks[bufferChunks.length - 1]);

  return JSON.stringify({
    strategy: memory.strategy ?? null,
    updatedAt: memory.updatedAt ?? null,
    stateGeneration: typeof state?.generation === 'number' ? state.generation : null,
    stateTokenCount: typeof state?.tokenCount === 'number' ? state.tokenCount : null,
    stateTriggerTokenCount:
      typeof state?.triggerTokenCount === 'number' ? state.triggerTokenCount : null,
    stateTimestamp: typeof state?.timestamp === 'string' ? state.timestamp : null,
    stateObservedUpToMessageId:
      typeof state?.observedUpToMessageId === 'string' ? state.observedUpToMessageId : null,
    stateContentLength:
      typeof state?.content === 'string' ? state.content.trim().length : null,
    latestObservationId: typeof latestStored?.id === 'string' ? latestStored.id : null,
    latestObservationGeneration:
      typeof latestStored?.generation === 'number' ? latestStored.generation : null,
    latestObservationTimestamp:
      typeof latestStored?.timestamp === 'string' ? latestStored.timestamp : null,
    latestObservationTokenCount:
      typeof latestStored?.tokenCount === 'number' ? latestStored.tokenCount : null,
    latestObservationTriggerTokenCount:
      typeof latestStored?.triggerTokenCount === 'number' ? latestStored.triggerTokenCount : null,
    latestObservationObservedUpToMessageId:
      typeof latestStored?.observedUpToMessageId === 'string' ? latestStored.observedUpToMessageId : null,
    latestObservationContentLength:
      typeof latestStored?.content === 'string' ? latestStored.content.trim().length : null,
    bufferChunkCount: bufferChunks.length,
    latestBufferObservedUpToMessageId:
      typeof latestBufferChunk?.observedUpToMessageId === 'string'
        ? latestBufferChunk.observedUpToMessageId
        : null,
    latestBufferObservedUpToTimestamp:
      typeof latestBufferChunk?.observedUpToTimestamp === 'string'
        ? latestBufferChunk.observedUpToTimestamp
        : null,
    latestBufferTokenCount:
      typeof latestBufferChunk?.tokenCount === 'number' ? latestBufferChunk.tokenCount : null,
    latestBufferContentLength:
      typeof latestBufferChunk?.content === 'string' ? latestBufferChunk.content.trim().length : null,
  });
}

function didMemorySnapshotChange(
  previous: ChatMemoryStateResponse | null | undefined,
  next: ChatMemoryStateResponse | null | undefined,
): boolean {
  return toMemorySnapshotSignature(previous) !== toMemorySnapshotSignature(next);
}

function toObservationTimeline(memory: ChatMemoryStateResponse): ObservationData[] {
  if (!memory.hasMemoryState || memory.strategy !== 'observational') return [];

  const state = asRecord(memory.state);
  const stateGeneration =
    typeof state?.generation === 'number' ? state.generation : undefined;

  const stored = (memory.observations ?? []).map((obs) => ({
    id: obs.id,
    hasObservations: true,
    generation: obs.generation,
    content: obs.content,
    tokenCount: obs.tokenCount,
    triggerTokenCount:
      typeof obs.triggerTokenCount === 'number' ? obs.triggerTokenCount : undefined,
    observedUpToMessageId: obs.observedUpToMessageId ?? undefined,
    currentTask: obs.currentTask ?? undefined,
    suggestedResponse: obs.suggestedResponse ?? undefined,
    timestamp: obs.timestamp,
    source: 'stored' as const,
  }));

  const buffer = asRecord(state?.buffer);
  const chunks = Array.isArray(buffer?.chunks) ? buffer.chunks : [];
  const buffered = chunks.flatMap((chunk, index) => {
    const raw = asRecord(chunk);
    if (!raw) return [];
    const content = typeof raw.content === 'string' ? raw.content.trim() : '';
    if (!content) return [];

    const observedUpToTimestamp =
      typeof raw.observedUpToTimestamp === 'string' ? raw.observedUpToTimestamp : undefined;
    const timestamp =
      observedUpToTimestamp
      ?? (typeof memory.updatedAt === 'string' ? memory.updatedAt : undefined)
      ?? new Date(0).toISOString();
    const tokenCount =
      typeof raw.tokenCount === 'number' && Number.isFinite(raw.tokenCount) && raw.tokenCount > 0
        ? raw.tokenCount
        : Math.max(1, Math.floor(content.length / 4));
    const triggerTokenCount =
      typeof raw.triggerTokenCount === 'number'
      && Number.isFinite(raw.triggerTokenCount)
      && raw.triggerTokenCount > 0
        ? raw.triggerTokenCount
        : undefined;

    return [
      {
        id: `buffer-${index}-${timestamp}-${typeof raw.observedUpToMessageId === 'string' ? raw.observedUpToMessageId : 'none'}`,
        hasObservations: true,
        generation:
          stateGeneration
          ?? (stored[0]?.generation ?? 0),
        content,
        tokenCount,
        triggerTokenCount,
        observedUpToMessageId:
          typeof raw.observedUpToMessageId === 'string' ? raw.observedUpToMessageId : undefined,
        observedUpToTimestamp,
        currentTask:
          typeof raw.currentTask === 'string' && raw.currentTask.trim() ? raw.currentTask.trim() : undefined,
        suggestedResponse:
          typeof raw.suggestedResponse === 'string' && raw.suggestedResponse.trim()
            ? raw.suggestedResponse.trim()
            : undefined,
        timestamp,
        source: 'buffered' as const,
      },
    ];
  });

  return [...stored, ...buffered].sort((a, b) => {
    const left = a.timestamp ? new Date(a.timestamp).getTime() : Number.NaN;
    const right = b.timestamp ? new Date(b.timestamp).getTime() : Number.NaN;
    return (Number.isNaN(left) ? 0 : left) - (Number.isNaN(right) ? 0 : right);
  });
}

function reconcileSubAgentRunsWithToolCalls(
  runs: SubAgentRun[],
  toolCalls: ToolCall[],
): SubAgentRun[] {
  if (runs.length === 0 || toolCalls.length === 0) return runs;

  const toolCallById = new Map(toolCalls.map((toolCall) => [toolCall.id, toolCall]));
  const reconciled: SubAgentRun[] = [];

  for (const run of runs) {
    const parentToolCall = toolCallById.get(run.toolCallId);
    if (!parentToolCall || parentToolCall.name !== 'spawn_sub_agent') {
      reconciled.push(run);
      continue;
    }

    const isInFlight = run.status === 'pending' || run.status === 'running';
    if (!isInFlight) {
      reconciled.push(run);
      continue;
    }

    if (parentToolCall.status === 'error') {
      const hasActivity = run.toolCalls.length > 0 || Boolean(run.output?.trim());
      if (!hasActivity) {
        // Spawn failed before the sub-agent produced any events; hide this empty run.
        continue;
      }
      reconciled.push({
        ...run,
        status: 'error',
        output: run.output ?? parentToolCall.output,
      });
      continue;
    }

    if (parentToolCall.status === 'completed') {
      reconciled.push({
        ...run,
        status: 'completed',
        output: run.output ?? parentToolCall.output,
      });
      continue;
    }

    reconciled.push(run);
  }

  return uniqueById(reconciled);
}

function applyObservationalContextOverlay(
  contextItems: ContextItem[],
  memory: ChatMemoryStateResponse | null,
  toolCalls: ToolCall[],
): ContextItem[] {
  if (!memory?.hasMemoryState || memory.strategy !== 'observational') return contextItems;

  const state = asRecord(memory.state);
  const latestStored = memory.observations?.[0];
  const observedUpToMessageId =
    typeof state?.observedUpToMessageId === 'string'
      ? state.observedUpToMessageId
      : typeof latestStored?.observedUpToMessageId === 'string'
        ? latestStored.observedUpToMessageId
        : undefined;
  if (!observedUpToMessageId) return contextItems;
  const observedUpToTimestamp =
    typeof state?.timestamp === 'string'
      ? state.timestamp
      : typeof latestStored?.timestamp === 'string'
        ? latestStored.timestamp
        : undefined;

  const observedConversationIds: string[] = [];
  for (const item of contextItems) {
    if (item.type !== 'conversation') continue;
    observedConversationIds.push(item.id);
    if (item.id === observedUpToMessageId) break;
  }
  if (
    observedConversationIds.length === 0
    || observedConversationIds[observedConversationIds.length - 1] !== observedUpToMessageId
  ) {
    return contextItems;
  }

  const content =
    typeof state?.content === 'string' && state.content.trim()
      ? state.content.trim()
      : typeof latestStored?.content === 'string'
        ? latestStored.content
        : '';
  if (!content) return contextItems;

  const generation =
    typeof state?.generation === 'number'
      ? state.generation
      : typeof latestStored?.generation === 'number'
        ? latestStored.generation
        : undefined;
  const tokenCount =
    typeof state?.tokenCount === 'number' && Number.isFinite(state.tokenCount) && state.tokenCount > 0
      ? state.tokenCount
      : typeof latestStored?.tokenCount === 'number' && Number.isFinite(latestStored.tokenCount) && latestStored.tokenCount > 0
        ? latestStored.tokenCount
        : Math.max(1, Math.floor(content.length / 4));
  const ts =
    typeof state?.timestamp === 'string'
      ? state.timestamp
      : typeof latestStored?.timestamp === 'string'
        ? latestStored.timestamp
        : typeof memory.updatedAt === 'string'
          ? memory.updatedAt
          : new Date(0).toISOString();

  const summaryItem: ContextItem = {
    id: `ctx-observation-${generation ?? 'unknown'}-${ts}`,
    type: 'summary',
    name: generation != null ? `Observational memory (gen ${generation})` : 'Observational memory',
    tokens: tokenCount,
    full_name: content,
  };

  const observedSet = new Set(observedConversationIds);
  const observedToolOutputIds = new Set(
    observedUpToTimestamp
      ? toolCalls
          .filter((toolCall) => Number.isFinite(toolCall.timestamp.getTime()))
          .filter((toolCall) => toolCall.timestamp.toISOString() <= observedUpToTimestamp)
          .map((toolCall) => toolCall.id)
      : [],
  );
  const out: ContextItem[] = [];
  let insertedSummary = false;
  for (const item of contextItems) {
    if (item.type === 'conversation' && observedSet.has(item.id)) {
      if (!insertedSummary) {
        out.push(summaryItem);
        insertedSummary = true;
      }
      continue;
    }
    if (item.type === 'tool_output' && observedToolOutputIds.has(item.id)) {
      if (!insertedSummary) {
        out.push(summaryItem);
        insertedSummary = true;
      }
      continue;
    }
    out.push(item);
  }
  return insertedSummary ? out : contextItems;
}

export function useChatHistory(chatId: string | null | undefined, client: ApiClient = defaultApi) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [subAgentRuns, setSubAgentRuns] = useState<SubAgentRun[]>([]);
  const [fileEdits, setFileEdits] = useState<FileEdit[]>([]);
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [reasoningBlocks, setReasoningBlocks] = useState<ReasoningBlock[]>([]);
  const [streamingReasoningBlockIds, setStreamingReasoningBlockIds] = useState<Set<string>>(new Set());
  const [contextItems, setContextItems] = useState<ContextItem[]>([]);
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [plans, setPlans] = useState<ProjectPlan[]>([]);
  const [verificationIssues, setVerificationIssues] = useState<Record<string, VerificationIssues>>({});
  const [maxTokens, setMaxTokens] = useState(128_000);
  const [model, setModel] = useState('Claude Sonnet 4');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processingChats, setProcessingChats] = useState<Set<string>>(new Set());
  const [observationStatus, setObservationStatus] = useState<ObservationStatus>('idle');
  const [observation, setObservation] = useState<ObservationData | null>(null);
  const [observations, setObservations] = useState<ObservationData[]>([]);
  const [persistentError, setPersistentError] = useState<ChatPersistentError | null>(null);

  const pendingContentDeltas = useRef<Map<string, string>>(new Map());
  const pendingReasoningDeltas = useRef<Map<string, string>>(new Map());
  const streamFlushScheduled = useRef(false);
  const contextRefreshTimer = useRef<number | null>(null);
  const baseContextItemsRef = useRef<ContextItem[]>([]);
  const memoryStateRef = useRef<ChatMemoryStateResponse | null>(null);
  const toolCallsRef = useRef<ToolCall[]>([]);
  const observationStatusVersionRef = useRef(0);
  const setMessagesRef = useRef(setMessages);
  const setReasoningBlocksRef = useRef(setReasoningBlocks);
  setMessagesRef.current = setMessages;
  setReasoningBlocksRef.current = setReasoningBlocks;

  const commitContextItems = useCallback(
    (
      nextBaseContextItems: ContextItem[],
      memoryOverride?: ChatMemoryStateResponse | null,
    ) => {
      baseContextItemsRef.current = nextBaseContextItems;
      const memorySnapshot = memoryOverride === undefined ? memoryStateRef.current : memoryOverride;
      setContextItems(
        applyObservationalContextOverlay(nextBaseContextItems, memorySnapshot, toolCallsRef.current),
      );
    },
    [],
  );

  const setContextItemsWithOverlay = useCallback(
    (next: ContextItem[] | ((prev: ContextItem[]) => ContextItem[])) => {
      const resolved =
        typeof next === 'function'
          ? (next as (prev: ContextItem[]) => ContextItem[])(baseContextItemsRef.current)
          : next;
      commitContextItems(resolved);
    },
    [commitContextItems],
  );

  useEffect(() => {
    toolCallsRef.current = toolCalls;
  }, [toolCalls]);

  useEffect(() => {
    observationStatusVersionRef.current += 1;
    if (contextRefreshTimer.current != null) {
      window.clearTimeout(contextRefreshTimer.current);
      contextRefreshTimer.current = null;
    }
    if (!isValidChatId(chatId)) {
      setLoading(false);
      setMessages([]);
      setToolCalls([]);
      toolCallsRef.current = [];
      setSubAgentRuns([]);
      setFileEdits([]);
      setCheckpoints([]);
      setReasoningBlocks([]);
      setStreamingReasoningBlockIds(new Set());
      memoryStateRef.current = null;
      commitContextItems([]);
      setTodos([]);
      setPlans([]);
      setVerificationIssues({});
      setObservationStatus('idle');
      setObservation(null);
      setObservations([]);
      setPersistentError(null);
      setError(null);
      pendingContentDeltas.current.clear();
      pendingReasoningDeltas.current.clear();
      streamFlushScheduled.current = false;
      return;
    }

    let cancelled = false;
    memoryStateRef.current = null;
    pendingContentDeltas.current.clear();
    pendingReasoningDeltas.current.clear();
    streamFlushScheduled.current = false;
    setLoading(true);
    setMessages([]);
    setToolCalls([]);
    toolCallsRef.current = [];
    setSubAgentRuns([]);
    setFileEdits([]);
    setCheckpoints([]);
    setReasoningBlocks([]);
    setStreamingReasoningBlockIds(new Set());
    commitContextItems([]);
    setPlans([]);
    setVerificationIssues({});
    setObservation(null);
    setObservations([]);
    setObservationStatus('idle');
    setPersistentError(null);

    Promise.all([
      client.getChatHistory(chatId),
      client.getMemoryState(chatId),
    ]).then(([histRes, obsRes]) => {
      if (cancelled) return;
      if (histRes.ok) {
        const d = histRes.data;
        const normalizedToolCalls = uniqueById(d.toolCalls.map(normalizeToolCall));
        setMessages(uniqueById(d.messages.map(normalizeMessage)));
        setToolCalls(normalizedToolCalls);
        toolCallsRef.current = normalizedToolCalls;
        setSubAgentRuns(
          reconcileSubAgentRunsWithToolCalls(
            uniqueById((d.subAgentRuns ?? []).map(normalizeSubAgentRun)),
            normalizedToolCalls,
          ),
        );
        setFileEdits(uniqueById(d.fileEdits.map(normalizeFileEdit)));
        setCheckpoints(uniqueById(d.checkpoints.map(normalizeCheckpoint)));
        setReasoningBlocks(uniqueById(d.reasoningBlocks.map(normalizeReasoningBlock)));
        setTodos((d.todos ?? []).map(normalizeTodo));
        setPlans(uniqueById((d.plans ?? []).map(normalizePlan)));
        setMaxTokens(d.maxTokens);
        setModel(d.model);
        setError(null);
      } else {
        setError(histRes.error ?? 'Failed to load chat history');
      }
      if (obsRes.ok) {
        memoryStateRef.current = obsRes.data;
        const nextObservation = toObservationData(obsRes.data);
        setObservation(nextObservation);
        setObservations(toObservationTimeline(obsRes.data));
      } else {
        memoryStateRef.current = null;
      }
      if (histRes.ok) {
        commitContextItems(histRes.data.contextItems, memoryStateRef.current);
      }
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [chatId, client, commitContextItems]);

  const sendMessage = useCallback(
    async (
      content: string,
      options?: {
        mode?: 'default' | 'planning' | 'plan_edit';
        activePlanId?: string;
        referencedFiles?: string[];
        attachments?: { data: string; mimeType: string; name?: string }[];
      },
    ) => {
      if (!isValidChatId(chatId)) {
        return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
      }
      setPersistentError(null);
      setProcessingChats((prev) => new Set(prev).add(chatId));
      try {
        const res = await client.sendMessage({
          chatId,
          content,
          mode: options?.mode,
          activePlanId: options?.activePlanId,
          referencedFiles: options?.referencedFiles,
          attachments: options?.attachments,
        });
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

  const continueAgent = useCallback(async () => {
    if (!isValidChatId(chatId)) {
      return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
    }
    setPersistentError(null);
    setProcessingChats((prev) => new Set(prev).add(chatId));
    try {
      return await client.continueAgent(chatId);
    } finally {
      setProcessingChats((prev) => {
        const next = new Set(prev);
        next.delete(chatId);
        return next;
      });
    }
  }, [chatId, client]);

  const isChatProcessing = useCallback(
    (targetChatId?: string) => {
      const id = targetChatId ?? chatId;
      return typeof id === 'string' ? processingChats.has(id) : false;
    },
    [processingChats, chatId],
  );

  const getProcessingChats = useCallback(
    () => Array.from(processingChats),
    [processingChats],
  );

  const cancelProcessing = useCallback(
    (targetChatId?: string) => {
      const id = targetChatId ?? chatId;
      if (typeof id !== 'string') return;
      client.cancelSession(id);
      client.cancelChat(id);
      setProcessingChats((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    },
    [chatId, client],
  );

  const approveCommand = useCallback(
    async (toolCallId: string) => {
      if (!isValidChatId(chatId)) {
        return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
      }
      const res = await client.approveCommand({ chatId, toolCallId });
      if (res.ok) {
        const nextToolCalls = toolCallsRef.current.map((toolCall) =>
          toolCall.id === toolCallId ? normalizeToolCall(res.data.toolCall) : toolCall,
        );
        toolCallsRef.current = nextToolCalls;
        setToolCalls(nextToolCalls);
        if (res.data.toolCall.name === 'spawn_sub_agent') {
          setSubAgentRuns((prev) =>
            reconcileSubAgentRunsWithToolCalls(prev, nextToolCalls),
          );
        }
        if (res.data.fileEdits.length) {
          setFileEdits((prev) =>
            uniqueById([...prev, ...res.data.fileEdits.map(normalizeFileEdit)]),
          );
        }
      }
      return res;
    },
    [chatId, client],
  );

  const rejectCommand = useCallback(
    async (toolCallId: string, reason?: string) => {
      if (!isValidChatId(chatId)) {
        return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
      }
      const res = await client.rejectCommand({ chatId, toolCallId, reason });
      if (res.ok) {
        const nextToolCalls = toolCallsRef.current.map((toolCall) =>
          toolCall.id === toolCallId ? { ...toolCall, status: 'error' as const } : toolCall,
        );
        toolCallsRef.current = nextToolCalls;
        setToolCalls(nextToolCalls);
        const rejectedToolCall = nextToolCalls.find((toolCall) => toolCall.id === toolCallId);
        if (rejectedToolCall?.name === 'spawn_sub_agent') {
          setSubAgentRuns((prev) =>
            reconcileSubAgentRunsWithToolCalls(prev, nextToolCalls),
          );
        }
      }
      return res;
    },
    [chatId, client],
  );

  const summarizeContext = useCallback(async () => {
    if (!isValidChatId(chatId)) {
      return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
    }
    const res = await client.summarizeContext({ chatId });
    if (res.ok) {
      commitContextItems(res.data.contextItems);
    }
    return res;
  }, [chatId, client, commitContextItems]);

  const removeContextItem = useCallback((itemId: string) => {
    commitContextItems(baseContextItemsRef.current.filter((i) => i.id !== itemId));
  }, [commitContextItems]);

  const resetTransientStreamState = useCallback(() => {
    pendingContentDeltas.current.clear();
    pendingReasoningDeltas.current.clear();
    streamFlushScheduled.current = false;
    setStreamingReasoningBlockIds(new Set());
  }, []);

  const refreshMemoryState = useCallback(
    async (targetChatId?: string | null) => {
      const resolvedChatId = targetChatId ?? chatId;
      if (!isValidChatId(resolvedChatId)) {
        memoryStateRef.current = null;
        setObservation(null);
        setObservations([]);
        commitContextItems(baseContextItemsRef.current, null);
        return { ok: true as const, snapshot: null as ChatMemoryStateResponse | null };
      }
      const res = await client.getMemoryState(resolvedChatId);
      if (res.ok) {
        memoryStateRef.current = res.data;
        setObservation(toObservationData(res.data));
        setObservations(toObservationTimeline(res.data));
        commitContextItems(baseContextItemsRef.current, res.data);
        return { ok: true as const, snapshot: res.data };
      } else {
        memoryStateRef.current = null;
        setObservation(null);
        setObservations([]);
        commitContextItems(baseContextItemsRef.current, null);
        return { ok: false as const, snapshot: null as ChatMemoryStateResponse | null };
      }
    },
    [chatId, client, commitContextItems],
  );

  const refreshContextFromHistory = useCallback(
    async (targetChatId?: string | null) => {
      const resolvedChatId = targetChatId ?? chatId;
      if (!isValidChatId(resolvedChatId)) return;
      const res = await client.getChatHistory(resolvedChatId);
      if (!res.ok) return;
      commitContextItems(res.data.contextItems);
      setMaxTokens(res.data.maxTokens);
      setModel(res.data.model);
    },
    [chatId, client, commitContextItems],
  );

  const revertToCheckpoint = useCallback(
    async (checkpointId: string) => {
      if (!isValidChatId(chatId)) {
        return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
      }
      const res = await client.revertToCheckpoint({ chatId, checkpointId });
      if (res.ok) {
        resetTransientStreamState();
        const normalizedToolCalls = uniqueById(res.data.toolCalls.map(normalizeToolCall));
        setMessages(uniqueById(res.data.messages.map(normalizeMessage)));
        setToolCalls(normalizedToolCalls);
        toolCallsRef.current = normalizedToolCalls;
        setSubAgentRuns(
          reconcileSubAgentRunsWithToolCalls(
            uniqueById((res.data.subAgentRuns ?? []).map(normalizeSubAgentRun)),
            normalizedToolCalls,
          ),
        );
        setFileEdits(uniqueById(res.data.fileEdits.map(normalizeFileEdit)));
        setCheckpoints(uniqueById(res.data.checkpoints.map(normalizeCheckpoint)));
        setReasoningBlocks(uniqueById(res.data.reasoningBlocks.map(normalizeReasoningBlock)));
        setTodos((res.data.todos ?? []).map(normalizeTodo));
        setVerificationIssues({});
        setObservationStatus('idle');
        setPersistentError(null);
        const plansRes = await client.getPlans(chatId);
        if (plansRes.ok) {
          setPlans(uniqueById((plansRes.data.plans ?? []).map(normalizePlan)));
        }
        await Promise.all([
          refreshContextFromHistory(chatId),
          refreshMemoryState(chatId),
        ]);
      }
      return res;
    },
    [chatId, client, refreshContextFromHistory, refreshMemoryState, resetTransientStreamState],
  );

  const revertFile = useCallback(
    async (fileEditId: string) => {
      if (!isValidChatId(chatId)) {
        return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
      }
      const res = await client.revertFile({ chatId, fileEditId });
      if (res.ok) {
        setFileEdits(uniqueById(res.data.fileEdits.map(normalizeFileEdit)));
      }
      return res;
    },
    [chatId, client],
  );

  const refreshPlans = useCallback(async () => {
    if (!isValidChatId(chatId)) {
      return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
    }
    const res = await client.getPlans(chatId);
    if (res.ok) {
      setPlans(uniqueById((res.data.plans ?? []).map(normalizePlan)));
    }
    return res;
  }, [chatId, client]);

  useEffect(() => {
    return () => {
      if (contextRefreshTimer.current != null) {
        window.clearTimeout(contextRefreshTimer.current);
        contextRefreshTimer.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!isValidChatId(chatId) || plans.length === 0) return () => {};
    const intervalId = window.setInterval(() => {
      void refreshPlans();
    }, 3000);
    return () => window.clearInterval(intervalId);
  }, [chatId, plans.length, refreshPlans]);

  const scheduleContextRefresh = useCallback(
    (targetChatId?: string | null, immediate = false) => {
      const resolvedChatId = targetChatId ?? chatId;
      if (!isValidChatId(resolvedChatId)) return;
      if (immediate) {
        if (contextRefreshTimer.current != null) {
          window.clearTimeout(contextRefreshTimer.current);
          contextRefreshTimer.current = null;
        }
        void refreshContextFromHistory(resolvedChatId);
        return;
      }
      if (contextRefreshTimer.current != null) return;
      contextRefreshTimer.current = window.setTimeout(() => {
        contextRefreshTimer.current = null;
        void refreshContextFromHistory(resolvedChatId);
      }, 250);
    },
    [chatId, refreshContextFromHistory],
  );

  const editMessage = useCallback(
    async (messageId: string, content: string, referencedFiles?: string[]) => {
      if (!isValidChatId(chatId)) {
        return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
      }
      const res = await client.editMessage({ chatId, messageId, content, referencedFiles });
      if (res.ok) {
        resetTransientStreamState();
        const d = res.data.revertedHistory;
        const normalizedToolCalls = uniqueById(d.toolCalls.map(normalizeToolCall));
        setMessages(uniqueById(d.messages.map(normalizeMessage)));
        setToolCalls(normalizedToolCalls);
        toolCallsRef.current = normalizedToolCalls;
        setSubAgentRuns(
          reconcileSubAgentRunsWithToolCalls(
            uniqueById((d.subAgentRuns ?? []).map(normalizeSubAgentRun)),
            normalizedToolCalls,
          ),
        );
        setFileEdits(uniqueById(d.fileEdits.map(normalizeFileEdit)));
        setCheckpoints(uniqueById(d.checkpoints.map(normalizeCheckpoint)));
        setReasoningBlocks(uniqueById(d.reasoningBlocks.map(normalizeReasoningBlock)));
        setTodos((d.todos ?? []).map(normalizeTodo));
        setVerificationIssues({});
        setObservationStatus('idle');
        setPersistentError(null);
        const plansRes = await client.getPlans(chatId);
        if (plansRes.ok) {
          setPlans(uniqueById((plansRes.data.plans ?? []).map(normalizePlan)));
        }
        await Promise.all([
          refreshContextFromHistory(chatId),
          refreshMemoryState(chatId),
        ]);
      }
      return res;
    },
    [chatId, client, refreshContextFromHistory, refreshMemoryState, resetTransientStreamState],
  );

  const updatePlan = useCallback(
    async (planId: string, content: string, options?: { title?: string; baseRevision?: number; lastEditor?: 'user' | 'agent' | 'external' }) => {
      if (!isValidChatId(chatId)) {
        return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
      }
      const res = await client.updatePlan({
        chatId,
        planId,
        content,
        title: options?.title,
        baseRevision: options?.baseRevision,
        lastEditor: options?.lastEditor ?? 'user',
      });
      if (res.ok) {
        const normalized = normalizePlan(res.data.plan);
        setPlans((prev) => upsertById(prev, normalized));
      }
      return res;
    },
    [chatId, client],
  );

  const approvePlan = useCallback(
    async (planId: string, action: 'keep_context' | 'clear_context') => {
      if (!isValidChatId(chatId)) {
        return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
      }
      const res = await client.approvePlan({ chatId, planId, action });
      if (res.ok) {
        const normalized = normalizePlan(res.data.plan);
        setPlans((prev) => upsertById(prev, normalized));
      }
      return res;
    },
    [chatId, client],
  );

  const retryObservation = useCallback(async () => {
    if (!isValidChatId(chatId)) {
      return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
    }
    const res = await client.retryMemory(chatId);
    if (res.ok) {
      setPersistentError(null);
      setObservationStatus('observing');
    }
    return res;
  }, [chatId, client]);

  const asDate = useCallback((value: string | Date): Date => (value instanceof Date ? value : new Date(value)), []);

  const flushStreamingDeltas = useCallback(() => {
    streamFlushScheduled.current = false;
    const contentDeltas = pendingContentDeltas.current;
    const reasoningDeltas = pendingReasoningDeltas.current;
    if (contentDeltas.size === 0 && reasoningDeltas.size === 0) return;
    pendingContentDeltas.current = new Map();
    pendingReasoningDeltas.current = new Map();
    if (contentDeltas.size > 0) {
      setMessagesRef.current((prev) => {
        let next = prev;
        for (const [messageId, delta] of contentDeltas) {
          const idx = next.findIndex((m) => m.id === messageId);
          if (idx === -1) {
            next = [
              ...next,
              {
                id: messageId,
                role: 'agent' as const,
                content: delta,
                timestamp: new Date(),
              },
            ];
          } else {
            const copy = [...next];
            copy[idx] = { ...copy[idx], content: copy[idx].content + delta };
            next = copy;
          }
        }
        return next;
      });
    }
    if (reasoningDeltas.size > 0) {
      setReasoningBlocksRef.current((prev) => {
        let next = prev;
        for (const [blockId, delta] of reasoningDeltas) {
          const idx = next.findIndex((rb) => rb.id === blockId);
          if (idx === -1) return next;
          const copy = [...next];
          copy[idx] = { ...copy[idx], content: copy[idx].content + delta };
          next = copy;
        }
        return next;
      });
    }
  }, []);

  const scheduleStreamFlush = useCallback(() => {
    if (streamFlushScheduled.current) return;
    streamFlushScheduled.current = true;
    requestAnimationFrame(flushStreamingDeltas);
  }, [flushStreamingDeltas]);

  const processEvent = useCallback(
    (event: AgentEvent) => {
      const updateById = <T extends { id: string }>(items: T[], next: T): T[] => {
        const idx = items.findIndex((item) => item.id === next.id);
        if (idx === -1) return [...items, next];
        const copy = [...items];
        copy[idx] = next;
        return copy;
      };

      switch (event.type) {
        case 'message': {
          const payload = event.payload as { message: Message };
          pendingContentDeltas.current.delete(payload.message.id);
          const message = normalizeMessage({ ...payload.message, timestamp: asDate(payload.message.timestamp) });
          setMessages((prev) => {
            const idx = prev.findIndex((m) => m.id === message.id);
            if (idx === -1) return [...prev, message];
            // Only replace if it's the last message (streaming update); otherwise append to preserve all agent messages
            if (idx === prev.length - 1) {
              const copy = [...prev];
              copy[idx] = message;
              return copy;
            }
            return [...prev, { ...message, id: `${message.id}-${Date.now()}` }];
          });
          scheduleContextRefresh(event.chatId, true);
          break;
        }
        case 'content_delta': {
          const payload = event.payload as { messageId: string; delta: string };
          if (payload.delta) {
            const map = pendingContentDeltas.current;
            map.set(payload.messageId, (map.get(payload.messageId) ?? '') + payload.delta);
            scheduleStreamFlush();
            scheduleContextRefresh(event.chatId);
          }
          break;
        }
        case 'tool_call_start':
        case 'tool_call_end': {
          const payload = event.payload as {
            toolCall?: ToolCall & { checkpointId?: string; duration_ms?: number };
            toolCallId?: string;
            toolName?: string;
            input?: Record<string, unknown>;
          };
          const toolCall = payload.toolCall ?? {
            id: payload.toolCallId ?? `tc-evt-${Date.now()}`,
            name: payload.toolName ?? 'unknown',
            status: 'pending' as const,
            input: payload.input ?? {},
            timestamp: new Date(),
            approvalRequired: false,
          };
          const tcWithTs = normalizeToolCall(toolCall);
          const nextToolCalls = updateById(toolCallsRef.current, tcWithTs);
          toolCallsRef.current = nextToolCalls;
          setToolCalls(nextToolCalls);
          if (event.type === 'tool_call_end') {
            if (tcWithTs.name === 'spawn_sub_agent') {
              setSubAgentRuns((prev) =>
                reconcileSubAgentRunsWithToolCalls(prev, nextToolCalls),
              );
            }
            scheduleContextRefresh(event.chatId);
          }
          const cpId = (payload.toolCall as { checkpointId?: string })?.checkpointId;
          if (cpId && tcWithTs.id) {
            setCheckpoints((prev) =>
              prev.map((cp) =>
                cp.id === cpId && !cp.toolCalls.includes(tcWithTs.id)
                  ? { ...cp, toolCalls: [...cp.toolCalls, tcWithTs.id] }
                  : cp,
              ),
            );
          }
          break;
        }
        case 'approval_required': {
          const payload = event.payload as {
            toolCall?: ToolCall & { checkpointId?: string };
            toolCallId?: string;
            toolName?: string;
            input?: Record<string, unknown>;
            description?: string;
            autoApproved?: boolean;
          };
          const toolCall = payload.toolCall ?? {
            id: payload.toolCallId ?? `tc-evt-${Date.now()}`,
            name: payload.toolName ?? 'unknown',
            status: payload.autoApproved ? ('running' as const) : ('pending' as const),
            input: payload.input ?? {},
            description: payload.description,
            approvalRequired: !payload.autoApproved,
            timestamp: new Date(),
          };
          const tcWithTs = {
            ...toolCall,
            timestamp: asDate(toolCall.timestamp),
            approvalRequired: payload.autoApproved ? false : (toolCall.approvalRequired ?? true),
            description: payload.description ?? toolCall.description,
          };
          const nextToolCalls = updateById(toolCallsRef.current, tcWithTs);
          toolCallsRef.current = nextToolCalls;
          setToolCalls(nextToolCalls);
          const cpId = (payload.toolCall as { checkpointId?: string })?.checkpointId;
          if (cpId && tcWithTs.id) {
            setCheckpoints((prev) =>
              prev.map((cp) =>
                cp.id === cpId && !cp.toolCalls.includes(tcWithTs.id)
                  ? { ...cp, toolCalls: [...cp.toolCalls, tcWithTs.id] }
                  : cp,
              ),
            );
          }
          break;
        }
        case 'file_edit': {
          const payload = event.payload as { fileEdit: FileEdit };
          const edit = { ...payload.fileEdit, timestamp: asDate(payload.fileEdit.timestamp) };
          setFileEdits((prev) => updateById(prev, edit));
          break;
        }
        case 'reasoning_start': {
          const payload = event.payload as { reasoningBlock: ReasoningBlock };
          if (payload.reasoningBlock) {
            const block = {
              ...payload.reasoningBlock,
              timestamp: asDate(payload.reasoningBlock.timestamp),
            };
            setReasoningBlocks((prev) => updateById(prev, block));
            setStreamingReasoningBlockIds((prev) => new Set(prev).add(block.id));
            const cpId = block.checkpointId;
            if (cpId && block.id) {
              setCheckpoints((prev) =>
                prev.map((cp) =>
                  cp.id === cpId && !(cp.reasoningBlocks ?? []).includes(block.id)
                    ? { ...cp, reasoningBlocks: [...(cp.reasoningBlocks ?? []), block.id] }
                    : cp,
                ),
              );
            }
          }
          break;
        }
        case 'reasoning_end': {
          const payload = event.payload as { reasoningBlock: ReasoningBlock & { tokens?: number } };
          if (payload.reasoningBlock) {
            pendingReasoningDeltas.current.delete(payload.reasoningBlock.id);
            const block = {
              ...payload.reasoningBlock,
              timestamp: asDate(payload.reasoningBlock.timestamp),
            };
            setReasoningBlocks((prev) => updateById(prev, block));
            setStreamingReasoningBlockIds((prev) => {
              const next = new Set(prev);
              next.delete(block.id);
              return next;
            });
            const cpId = block.checkpointId;
            if (cpId && block.id) {
              setCheckpoints((prev) =>
                prev.map((cp) =>
                  cp.id === cpId && !(cp.reasoningBlocks ?? []).includes(block.id)
                    ? { ...cp, reasoningBlocks: [...(cp.reasoningBlocks ?? []), block.id] }
                    : cp,
                ),
              );
            }
            // Refresh context so reasoning block tokens appear in the usage display.
            // The backend commits the block before publishing this event, so it is
            // safe to fetch immediately.
            scheduleContextRefresh(event.chatId, true);
          }
          break;
        }
        case 'reasoning_delta': {
          const payload = event.payload as { reasoningBlockId: string; delta: string };
          if (payload.reasoningBlockId && payload.delta) {
            const map = pendingReasoningDeltas.current;
            map.set(payload.reasoningBlockId, (map.get(payload.reasoningBlockId) ?? '') + payload.delta);
            scheduleStreamFlush();
          }
          break;
        }
        case 'checkpoint': {
          const payload = event.payload as { checkpoint: Checkpoint };
          const checkpoint = { ...payload.checkpoint, timestamp: asDate(payload.checkpoint.timestamp) };
          setCheckpoints((prev) => updateById(prev, checkpoint));
          break;
        }
        case 'context_update': {
          const payload = event.payload as { contextItems: ContextItem[] };
          commitContextItems(payload.contextItems);
          break;
        }
        case 'verification_issues': {
          const payload = event.payload as VerificationIssues;
          setVerificationIssues((prev) => ({ ...prev, [payload.checkpointId]: payload }));
          break;
        }
        case 'message_edited': {
          const payload = event.payload as unknown as {
            revertedHistory: {
              messages: Message[];
              toolCalls: ToolCall[];
              subAgentRuns?: SubAgentRun[];
              fileEdits: FileEdit[];
              checkpoints: Checkpoint[];
              reasoningBlocks: ReasoningBlock[];
              todos?: TodoItem[];
            };
            messageId?: string;
            content?: string;
            referencedFiles?: string[];
          };
          resetTransientStreamState();
          const normalizedToolCalls = uniqueById(payload.revertedHistory.toolCalls.map(normalizeToolCall));
          setMessages(
            uniqueById(payload.revertedHistory.messages.map(normalizeMessage)).map((message) =>
              message.id === payload.messageId
                ? {
                    ...message,
                    content: payload.content ?? message.content,
                    referencedFiles: Array.isArray(payload.referencedFiles)
                      ? payload.referencedFiles
                      : (message.referencedFiles ?? []),
                  }
                : message,
            ),
          );
          setToolCalls(normalizedToolCalls);
          toolCallsRef.current = normalizedToolCalls;
          setSubAgentRuns(
            reconcileSubAgentRunsWithToolCalls(
              uniqueById((payload.revertedHistory.subAgentRuns ?? []).map(normalizeSubAgentRun)),
              normalizedToolCalls,
            ),
          );
          setFileEdits(uniqueById(payload.revertedHistory.fileEdits.map(normalizeFileEdit)));
          setCheckpoints(uniqueById(payload.revertedHistory.checkpoints.map(normalizeCheckpoint)));
          setReasoningBlocks(uniqueById(payload.revertedHistory.reasoningBlocks.map(normalizeReasoningBlock)));
          setTodos((payload.revertedHistory.todos ?? []).map(normalizeTodo));
          setVerificationIssues({});
          setObservationStatus('idle');
          setPersistentError(null);
          void client.getPlans(event.chatId).then((plansRes) => {
            if (plansRes.ok) {
              setPlans(uniqueById((plansRes.data.plans ?? []).map(normalizePlan)));
            }
          });
          void Promise.all([
            refreshContextFromHistory(event.chatId),
            refreshMemoryState(event.chatId),
          ]);
          break;
        }
        case 'todo_list_updated': {
          const payload = event.payload as unknown as { todos: TodoItem[] };
          if (payload.todos) {
            setTodos(payload.todos.map(normalizeTodo));
          }
          break;
        }
        case 'plan_ready':
        case 'plan_updated':
        case 'plan_approved': {
          const payload = event.payload as AgentPlanPayload;
          if (payload.plan) {
            const normalized = normalizePlan(payload.plan);
            setPlans((prev) => upsertById(prev, normalized));
          }
          break;
        }
        case 'plan_conflict': {
          const payload = event.payload as AgentPlanConflictPayload;
          if (payload.plan) {
            const normalized = normalizePlan(payload.plan);
            setPlans((prev) => upsertById(prev, normalized));
          }
          break;
        }
        case 'plan_started':
          break;
        case 'observation_status': {
          const payload = event.payload as AgentObservationStatusPayload;
          if (payload.status === 'observing') {
            observationStatusVersionRef.current += 1;
            setObservationStatus('observing');
            setPersistentError((prev) => (prev?.source === 'observer' ? null : prev));
          } else if (payload.status === 'reflecting') {
            observationStatusVersionRef.current += 1;
            setObservationStatus('reflecting');
          } else if (payload.status === 'observed' || payload.status === 'reflected') {
            setPersistentError((prev) => (prev?.source === 'observer' || prev?.source === 'reflector' ? null : prev));
            // Refresh observation data and re-derive visible context immediately.
            const previousMemorySnapshot = memoryStateRef.current;
            const statusVersion = observationStatusVersionRef.current + 1;
            observationStatusVersionRef.current = statusVersion;
            if (event.chatId) {
              void refreshMemoryState(event.chatId).then((refreshResult) => {
                if (observationStatusVersionRef.current !== statusVersion) return;
                const memoryUpdated =
                  refreshResult.ok && didMemorySnapshotChange(previousMemorySnapshot, refreshResult.snapshot);
                setObservationStatus(memoryUpdated ? 'done' : 'idle');
                scheduleContextRefresh(event.chatId, true);
              });
            } else {
              setObservationStatus('idle');
            }
          }
          break;
        }
        case 'sub_agent_start': {
          const payload = event.payload as unknown as {
            subAgentId: string;
            task: string;
            model: string;
            toolCallId: string;
          };
          const parentToolCall = toolCallsRef.current.find((toolCall) => toolCall.id === payload.toolCallId);
          if (
            parentToolCall?.name === 'spawn_sub_agent'
            && (parentToolCall.status === 'error' || parentToolCall.status === 'completed')
          ) {
            break;
          }
          const run: SubAgentRun = {
            id: payload.subAgentId,
            task: payload.task,
            model: payload.model,
            status: 'running',
            toolCalls: [],
            timestamp: new Date(),
            toolCallId: payload.toolCallId,
          };
          setSubAgentRuns((prev) => upsertById(prev, run));
          break;
        }
        case 'sub_agent_progress': {
          const payload = event.payload as unknown as { subAgentId: string };
          setSubAgentRuns((prev) =>
            prev.map((r) =>
              r.id === payload.subAgentId ? { ...r, status: 'running' as const } : r,
            ),
          );
          break;
        }
        case 'sub_agent_tool_call': {
          const payload = event.payload as {
            subAgentId: string;
            toolCall: ToolCall & { duration?: number };
          };
          const tc = normalizeToolCall(payload.toolCall as ToolCall & { duration_ms?: number });
          setSubAgentRuns((prev) =>
            prev.map((r) =>
              r.id === payload.subAgentId
                ? {
                    ...r,
                    toolCalls: upsertById(r.toolCalls, tc),
                  }
                : r,
            ),
          );
          break;
        }
        case 'sub_agent_end': {
          const payload = event.payload as unknown as {
            subAgentId: string;
            status: string;
            output: string;
            duration: number;
          };
          const status = ['pending', 'running', 'completed', 'error', 'cancelled', 'max_iterations'].includes(
            payload.status,
          )
            ? (payload.status as SubAgentRun['status'])
            : ('error' as SubAgentRun['status']);
          setSubAgentRuns((prev) =>
            prev.map((r) =>
              r.id === payload.subAgentId
                ? {
                    ...r,
                    status,
                    output: payload.output,
                    duration: payload.duration,
                  }
                : r,
            ),
          );
          scheduleContextRefresh(event.chatId, true);
          break;
        }
        case 'agent_done': {
          setPersistentError(null);
          scheduleContextRefresh(event.chatId, true);
          break;
        }
        case 'error': {
          const payload = event.payload as AgentErrorPayload;
          if (payload.toolCallId) {
            const nextToolCalls = toolCallsRef.current.map((toolCall) =>
              toolCall.id === payload.toolCallId
                ? { ...toolCall, status: 'error' as const, output: payload.message ?? toolCall.output }
                : toolCall,
            );
            toolCallsRef.current = nextToolCalls;
            setToolCalls(nextToolCalls);
            const erroredToolCall = nextToolCalls.find((toolCall) => toolCall.id === payload.toolCallId);
            if (erroredToolCall?.name === 'spawn_sub_agent') {
              setSubAgentRuns((prev) =>
                reconcileSubAgentRunsWithToolCalls(prev, nextToolCalls),
              );
            }
          } else {
            setPersistentError({
              message: payload.message ?? 'An error occurred.',
              source: payload.source,
              retryable: payload.retryable ?? payload.retryAction === 'retry_observation',
              retryAction: payload.retryAction,
            });
            if (payload.source === 'observer' || payload.source === 'reflector') {
              setObservationStatus('idle');
            }
          }
          break;
        }
        default:
          break;
      }
    },
    [asDate, scheduleContextRefresh, scheduleStreamFlush, refreshContextFromHistory, refreshMemoryState, resetTransientStreamState],
  );

  return {
    messages,
    toolCalls,
    subAgentRuns,
    fileEdits,
    checkpoints,
    todos,
    plans,
    reasoningBlocks,
    streamingReasoningBlockIds,
    contextItems,
    verificationIssues,
    observationStatus,
    observation,
    observations,
    persistentError,
    maxTokens,
    model,
    loading,
    error,
    sendMessage,
    continueAgent,
    approveCommand,
    rejectCommand,
    summarizeContext,
    removeContextItem,
    revertToCheckpoint,
    revertFile,
    editMessage,
    refreshPlans,
    updatePlan,
    approvePlan,
    isChatProcessing,
    getProcessingChats,
    cancelProcessing,
    retryObservation,
    setMessages,
    setToolCalls,
    setFileEdits,
    setCheckpoints,
    setReasoningBlocks,
    setContextItems: setContextItemsWithOverlay,
    setModel,
    setMaxTokens,
    processEvent,
  };
}
