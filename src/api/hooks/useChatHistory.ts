/**
 * Fetches the complete chat history for a given chatId and provides
 * mutable state + action dispatchers for the full agent session.
 */

import { useState, useEffect, useCallback } from 'react';
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
import type { Message, ToolCall, FileEdit, Checkpoint, ContextItem, ReasoningBlock } from '@/types';
import type { AgentEvent } from '@/api/types';

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
          setFileEdits((prev) => [...prev, ...res.data.fileEdits.map(normalizeFileEdit)]);
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

  const asDate = useCallback((value: string | Date): Date => (value instanceof Date ? value : new Date(value)), []);

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
          const message = { ...payload.message, timestamp: asDate(payload.message.timestamp) };
          setMessages((prev) => updateById(prev, message));
          break;
        }
        case 'content_delta': {
          const payload = event.payload as { messageId: string; delta: string };
          setMessages((prev) => {
            const idx = prev.findIndex((m) => m.id === payload.messageId);
            if (idx === -1) {
              const placeholder: Message = {
                id: payload.messageId,
                role: 'agent',
                content: payload.delta,
                timestamp: new Date(),
              };
              return [...prev, placeholder];
            }
            const m = prev[idx];
            const updated = { ...m, content: m.content + payload.delta };
            const copy = [...prev];
            copy[idx] = updated;
            return copy;
          });
          break;
        }
        case 'tool_call_start':
        case 'tool_call_end': {
          const payload = event.payload as {
            toolCall?: ToolCall & { checkpointId?: string };
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
          const tcWithTs = { ...toolCall, timestamp: asDate(toolCall.timestamp) };
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
        case 'reasoning_start':
        case 'reasoning_end': {
          const payload = event.payload as { reasoningBlock: ReasoningBlock };
          if (payload.reasoningBlock) {
            const block = {
              ...payload.reasoningBlock,
              timestamp: asDate(payload.reasoningBlock.timestamp),
            };
            setReasoningBlocks((prev) => updateById(prev, block));
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
            setReasoningBlocks((prev) => {
              const idx = prev.findIndex((rb) => rb.id === payload.reasoningBlockId);
              if (idx === -1) return prev;
              const copy = [...prev];
              copy[idx] = { ...copy[idx], content: copy[idx].content + payload.delta };
              return copy;
            });
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
    [asDate],
  );

  return {
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
    sendMessage,
    approveCommand,
    rejectCommand,
    summarizeContext,
    removeContextItem,
    revertToCheckpoint,
    revertFile,
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
