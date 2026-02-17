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
    (targetChatId?: string) => processingChats.has(targetChatId ?? chatId),
    [processingChats, chatId],
  );

  const getProcessingChats = useCallback(
    () => Array.from(processingChats),
    [processingChats],
  );

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

  const summarizeContext = useCallback(async () => {
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
      const res = await client.revertFile({ chatId, fileEditId });
      if (res.ok) {
        setFileEdits(uniqueById(res.data.fileEdits.map(normalizeFileEdit)));
      }
      return res;
    },
    [chatId, client],
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
  };
}
