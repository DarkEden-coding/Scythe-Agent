/**
 * Hook for managing OpenRouter configuration.
 * Provides state and methods for API key management, connection testing,
 * and model syncing.
 */

import { useState, useEffect, useCallback } from 'react';
import { api as defaultApi, ApiClient } from '@/api/client';
import type { OpenRouterConfig } from '@/api/types';

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
    async (apiKey: string) => {
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

  const testConnection = useCallback(async () => {
    setTesting(true);
    setError(null);
    const res = await client.testOpenRouterConnection();
    if (!res.ok) {
      setError(res.error ?? 'Connection test failed');
    }
    setTesting(false);
    return res;
  }, [client]);

  const syncModels = useCallback(async () => {
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
