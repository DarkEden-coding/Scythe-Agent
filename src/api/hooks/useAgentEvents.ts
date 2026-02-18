/**
 * Subscribes to the real-time agent event stream for one or more chats.
 * Calls `onEvent` for each received event.
 * Subscribes to all valid chat IDs so agent_done for background chats is received.
 */

import { useEffect, useMemo, useRef } from 'react';
import { api as defaultApi, ApiClient } from '@/api/client';
import { isValidChatId } from '@/api/normalizers';
import type { AgentEvent } from '@/api/types';

export function useAgentEvents(
  chatIds: Iterable<string | null | undefined>,
  onEvent: (event: AgentEvent) => void,
  client: ApiClient = defaultApi,
) {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const ids = useMemo(
    () =>
      [...new Set([...chatIds].filter((id): id is string => isValidChatId(id)))].sort(
        (a, b) => a.localeCompare(b),
      ),
    [chatIds],
  );
  const depsKey = ids.join(',');

  useEffect(() => {
    if (ids.length === 0) return () => {};
    const unsubscribes = ids.map((id) =>
      client.subscribeToAgentEvents(id, (event) => {
        onEventRef.current(event);
      }),
    );
    return () => unsubscribes.forEach((u) => u());
  }, [depsKey, client]);
}
