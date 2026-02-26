/**
 * Shared API normalization helpers.
 */

import { useState, useCallback } from 'react';
import type { ApiResponse } from './types';
import type {
  Message,
  SubAgentRun,
  ToolCall,
  FileEdit,
  Checkpoint,
  ReasoningBlock,
  TodoItem,
  ProjectPlan,
} from '@/types';

export const toDate = (value: Date | string): Date =>
  value instanceof Date ? value : new Date(value);

export const normalizeMessage = (m: Message): Message => ({
  ...m,
  timestamp: toDate(m.timestamp),
  referencedFiles: Array.isArray(m.referencedFiles) ? m.referencedFiles : [],
  attachments: Array.isArray(m.attachments) ? m.attachments : [],
});

export const normalizeToolCall = (tc: ToolCall & { duration_ms?: number }): ToolCall => ({
  ...tc,
  timestamp: toDate(tc.timestamp),
  duration: tc.duration ?? tc.duration_ms ?? undefined,
});

export const normalizeFileEdit = (fe: FileEdit): FileEdit => ({
  ...fe,
  timestamp: toDate(fe.timestamp),
});

export const normalizeCheckpoint = (cp: Checkpoint): Checkpoint => ({
  ...cp,
  timestamp: toDate(cp.timestamp),
});

export const normalizeReasoningBlock = (rb: ReasoningBlock): ReasoningBlock => ({
  ...rb,
  timestamp: toDate(rb.timestamp),
});

export const normalizeSubAgentRun = (
  r: SubAgentRun & { duration?: number; output?: string }
): SubAgentRun => ({
  ...r,
  timestamp: toDate(r.timestamp),
  duration: r.duration ?? undefined,
  output: r.output ?? undefined,
  toolCalls: (r.toolCalls ?? []).map((tc) =>
    normalizeToolCall(tc as ToolCall & { duration_ms?: number })
  ),
});

export const normalizeTodo = (t: TodoItem): TodoItem => ({
  ...t,
  timestamp: toDate(t.timestamp),
});

export const normalizePlan = (p: ProjectPlan): ProjectPlan => ({
  ...p,
  createdAt: toDate(p.createdAt),
  updatedAt: toDate(p.updatedAt),
});

export const upsertById = <T extends { id: string }>(items: T[], next: T): T[] => {
  const idx = items.findIndex((item) => item.id === next.id);
  if (idx === -1) return [...items, next];
  const copy = [...items];
  copy[idx] = next;
  return copy;
};

export const uniqueById = <T extends { id: string }>(items: T[]): T[] =>
  items.filter((item, idx, all) => all.findIndex((candidate) => candidate.id === item.id) === idx);

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useAsyncState<T>(
  initial: T | null = null
): [AsyncState<T>, (p: Promise<ApiResponse<T>>) => Promise<ApiResponse<T>>] {
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

export const isValidChatId = (id: string | null | undefined): id is string =>
  typeof id === 'string' && id.length > 0;
