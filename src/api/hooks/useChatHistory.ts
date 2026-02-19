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
  upsertById,
  uniqueById,
  isValidChatId,
} from '@/api/normalizers';
import type {
  Message,
  ToolCall,
  FileEdit,
  Checkpoint,
  ContextItem,
  ReasoningBlock,
  VerificationIssues,
} from '@/types';
import type { AgentEvent } from '@/api/types';

export function useChatHistory(chatId: string | null | undefined, client: ApiClient = defaultApi) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [fileEdits, setFileEdits] = useState<FileEdit[]>([]);
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [reasoningBlocks, setReasoningBlocks] = useState<ReasoningBlock[]>([]);
  const [streamingReasoningBlockIds, setStreamingReasoningBlockIds] = useState<Set<string>>(new Set());
  const [contextItems, setContextItems] = useState<ContextItem[]>([]);
  const [verificationIssues, setVerificationIssues] = useState<Record<string, VerificationIssues>>({});
  const [maxTokens, setMaxTokens] = useState(128_000);
  const [model, setModel] = useState('Claude Sonnet 4');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processingChats, setProcessingChats] = useState<Set<string>>(new Set());

  const pendingContentDeltas = useRef<Map<string, string>>(new Map());
  const pendingReasoningDeltas = useRef<Map<string, string>>(new Map());
  const streamFlushScheduled = useRef(false);
  const setMessagesRef = useRef(setMessages);
  const setReasoningBlocksRef = useRef(setReasoningBlocks);
  setMessagesRef.current = setMessages;
  setReasoningBlocksRef.current = setReasoningBlocks;

  useEffect(() => {
    if (!isValidChatId(chatId)) {
      setLoading(false);
      setMessages([]);
      setToolCalls([]);
      setFileEdits([]);
      setCheckpoints([]);
      setReasoningBlocks([]);
      setStreamingReasoningBlockIds(new Set());
      setContextItems([]);
      setVerificationIssues({});
      setError(null);
      pendingContentDeltas.current.clear();
      pendingReasoningDeltas.current.clear();
      streamFlushScheduled.current = false;
      return;
    }

    let cancelled = false;
    pendingContentDeltas.current.clear();
    pendingReasoningDeltas.current.clear();
    streamFlushScheduled.current = false;
    setLoading(true);
    setMessages([]);
    setToolCalls([]);
    setFileEdits([]);
    setCheckpoints([]);
    setReasoningBlocks([]);
    setStreamingReasoningBlockIds(new Set());
    setContextItems([]);
    setVerificationIssues({});

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
        setToolCalls((prev) =>
          prev.map((tc) => (tc.id === toolCallId ? normalizeToolCall(res.data.toolCall) : tc)),
        );
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

  const summarizeContext = useCallback(async () => {
    if (!isValidChatId(chatId)) {
      return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
    }
    const res = await client.summarizeContext({ chatId });
    if (res.ok) {
      setContextItems(res.data.contextItems);
    }
    return res;
  }, [chatId, client]);

  const removeContextItem = useCallback((itemId: string) => {
    setContextItems((prev) => prev.filter((i) => i.id !== itemId));
  }, []);

  const revertToCheckpoint = useCallback(
    async (checkpointId: string) => {
      if (!isValidChatId(chatId)) {
        return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
      }
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

  const editMessage = useCallback(
    async (messageId: string, content: string) => {
      if (!isValidChatId(chatId)) {
        return { ok: false as const, data: null, error: 'No chat selected', timestamp: new Date().toISOString() };
      }
      const res = await client.editMessage({ chatId, messageId, content });
      if (res.ok) {
        const d = res.data.revertedHistory;
        setMessages(uniqueById(d.messages.map(normalizeMessage)));
        setToolCalls(uniqueById(d.toolCalls.map(normalizeToolCall)));
        setFileEdits(uniqueById(d.fileEdits.map(normalizeFileEdit)));
        setCheckpoints(uniqueById(d.checkpoints.map(normalizeCheckpoint)));
        setReasoningBlocks(uniqueById(d.reasoningBlocks.map(normalizeReasoningBlock)));
      }
      return res;
    },
    [chatId, client],
  );

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
          const message = { ...payload.message, timestamp: asDate(payload.message.timestamp) };
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
          break;
        }
        case 'content_delta': {
          const payload = event.payload as { messageId: string; delta: string };
          if (payload.delta) {
            const map = pendingContentDeltas.current;
            map.set(payload.messageId, (map.get(payload.messageId) ?? '') + payload.delta);
            scheduleStreamFlush();
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
          setToolCalls((prev) => updateById(prev, tcWithTs));
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
          setToolCalls((prev) => updateById(prev, tcWithTs));
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
          const payload = event.payload as { reasoningBlock: ReasoningBlock };
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
          setContextItems(payload.contextItems);
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
              fileEdits: FileEdit[];
              checkpoints: Checkpoint[];
              reasoningBlocks: ReasoningBlock[];
            };
          };
          setMessages(uniqueById(payload.revertedHistory.messages.map(normalizeMessage)));
          setToolCalls(uniqueById(payload.revertedHistory.toolCalls.map(normalizeToolCall)));
          setFileEdits(uniqueById(payload.revertedHistory.fileEdits.map(normalizeFileEdit)));
          setCheckpoints(uniqueById(payload.revertedHistory.checkpoints.map(normalizeCheckpoint)));
          setReasoningBlocks(uniqueById(payload.revertedHistory.reasoningBlocks.map(normalizeReasoningBlock)));
          break;
        }
        case 'error': {
          const payload = event.payload as {
            message?: string;
            toolCallId?: string;
            toolName?: string;
          };
          if (payload.toolCallId) {
            setToolCalls((prev) =>
              prev.map((tc) =>
                tc.id === payload.toolCallId
                  ? { ...tc, status: 'error' as const, output: payload.message ?? tc.output }
                  : tc,
              ),
            );
          }
          break;
        }
        default:
          break;
      }
    },
    [asDate, scheduleStreamFlush],
  );

  return {
    messages,
    toolCalls,
    fileEdits,
    checkpoints,
    reasoningBlocks,
    streamingReasoningBlockIds,
    contextItems,
    verificationIssues,
    maxTokens,
    model,
    loading,
    error,
    sendMessage,
    approveCommand,
    rejectCommand,
    summarizeContext,
    removeContextItem,
    revertToCheckpoint,
    revertFile,
    editMessage,
    isChatProcessing,
    getProcessingChats,
    cancelProcessing,
    setMessages,
    setToolCalls,
    setFileEdits,
    setCheckpoints,
    setReasoningBlocks,
    setContextItems,
    setModel,
    setMaxTokens,
    processEvent,
  };
}
