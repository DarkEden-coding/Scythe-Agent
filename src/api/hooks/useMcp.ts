/**
 * Hook for managing MCP servers and tools.
 */

import { useState, useEffect, useCallback } from 'react';
import { api as defaultApi, ApiClient } from '@/api/client';
import type { MCPServer, CreateMCPServerRequest, UpdateMCPServerRequest } from '@/api/types';

export function useMcp(client: ApiClient = defaultApi) {
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchServers = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await client.getMcpServers();
    if (res.ok) {
      setServers(res.data.servers);
    } else {
      setError(res.error ?? 'Failed to load MCP servers');
    }
    setLoading(false);
    return res;
  }, [client]);

  useEffect(() => {
    fetchServers();
  }, [fetchServers]);

  const createServer = useCallback(
    async (req: CreateMCPServerRequest) => {
      setLoading(true);
      setError(null);
      const res = await client.createMcpServer(req);
      if (res.ok) {
        setServers((prev) => [...prev, res.data]);
      } else {
        setError(res.error ?? 'Failed to create server');
      }
      setLoading(false);
      return res;
    },
    [client],
  );

  const updateServer = useCallback(
    async (serverId: string, req: UpdateMCPServerRequest) => {
      setError(null);
      const res = await client.updateMcpServer(serverId, req);
      if (res.ok) {
        setServers((prev) =>
          prev.map((s) => (s.id === serverId ? res.data : s)),
        );
      } else {
        setError(res.error ?? 'Failed to update server');
      }
      return res;
    },
    [client],
  );

  const deleteServer = useCallback(
    async (serverId: string) => {
      setError(null);
      const res = await client.deleteMcpServer(serverId);
      if (res.ok) {
        setServers((prev) => prev.filter((s) => s.id !== serverId));
      } else {
        setError(res.error ?? 'Failed to delete server');
      }
      return res;
    },
    [client],
  );

  const setServerEnabled = useCallback(
    async (serverId: string, enabled: boolean) => {
      setError(null);
      const res = await client.setMcpServerEnabled(serverId, enabled);
      if (res.ok) {
        setServers((prev) =>
          prev.map((s) => (s.id === serverId ? res.data : s)),
        );
      } else {
        setError(res.error ?? 'Failed to update server');
      }
      return res;
    },
    [client],
  );

  const setToolEnabled = useCallback(
    async (toolId: string, enabled: boolean) => {
      setError(null);
      const res = await client.setMcpToolEnabled(toolId, enabled);
      if (res.ok) {
        const { serverId } = res.data;
        setServers((prev) =>
          prev.map((s) =>
            s.id === serverId
              ? {
                  ...s,
                  tools: s.tools.map((t) =>
                    t.id === toolId ? { ...t, enabled } : t,
                  ),
                }
              : s,
          ),
        );
      } else {
        setError(res.error ?? 'Failed to update tool');
      }
      return res;
    },
    [client],
  );

  const refreshTools = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    const res = await client.refreshMcpTools();
    if (res.ok) {
      await fetchServers();
      const discoveryErrors = res.data?.errors;
      if (discoveryErrors?.length) {
        setError(discoveryErrors.join(' '));
      } else {
        setError(null);
      }
    } else {
      setError(res.error ?? 'Refresh failed');
    }
    setRefreshing(false);
    return res;
  }, [client, fetchServers]);

  return {
    servers,
    loading,
    refreshing,
    error,
    fetchServers,
    createServer,
    updateServer,
    deleteServer,
    setServerEnabled,
    setToolEnabled,
    refreshTools,
  };
}
