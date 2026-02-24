/**
 * Hook for managing Brave Search API key configuration.
 */

import { useState, useEffect, useCallback } from 'react';
import { api as defaultApi, ApiClient } from '@/api/client';
import type { BraveConfig } from '@/api/types';

export function useBrave(client: ApiClient = defaultApi) {
  const [config, setConfig] = useState<BraveConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await client.getBraveConfig();
    if (res.ok) {
      setConfig(res.data);
    } else {
      setError(res.error ?? 'Failed to load Brave config');
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
      const res = await client.setBraveApiKey({ apiKey });
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

  return {
    config,
    loading,
    error,
    setApiKey,
    refreshConfig,
  };
}
