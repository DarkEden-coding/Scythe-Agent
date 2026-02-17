/**
 * Subscribes to the real-time agent event stream for a given chat.
 * Calls `onEvent` for each received event.
 * Skips subscription when chatId is invalid.
 */

import { useEffect, useRef } from 'react';
import { api as defaultApi, ApiClient } from '@/api/client';
import { isValidChatId } from '@/api/normalizers';
import type { AgentEvent } from '@/api/types';

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
