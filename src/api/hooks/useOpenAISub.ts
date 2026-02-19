/**
 * Hook for managing OpenAI Subscription (OAuth) configuration.
 * Provides state and methods for sign-in, connection testing, and model syncing.
 */

import { useState, useEffect, useCallback } from 'react';
import { api as defaultApi, ApiClient } from '@/api/client';
import type { OpenAISubConfig } from '@/api/types';

export function useOpenAISub(client: ApiClient = defaultApi) {
  const [config, setConfig] = useState<OpenAISubConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await client.getOpenAISubConfig();
    if (res.ok) {
      setConfig(res.data);
    } else {
      setError(res.error ?? 'Failed to load OpenAI Sub config');
    }
    setLoading(false);
    return res;
  }, [client]);

  useEffect(() => {
    refreshConfig();
  }, [refreshConfig]);

  useEffect(() => {
    const handler = () => refreshConfig();
    window.addEventListener('openai-sub-auth-done', handler);
    return () => window.removeEventListener('openai-sub-auth-done', handler);
  }, [refreshConfig]);

  const startSignIn = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await client.getOpenAISubAuthStart();
    if (res.ok && res.data.authUrl) {
      window.open(res.data.authUrl, '_blank', 'noopener,noreferrer,width=500,height=700');
    } else {
      setError(res.error ?? 'Failed to start sign-in');
    }
    setLoading(false);
    return res;
  }, [client]);

  const testConnection = useCallback(async () => {
    setTesting(true);
    setError(null);
    const res = await client.testOpenAISubConnection();
    if (!res.ok) {
      setError(res.error ?? 'Connection test failed');
    }
    setTesting(false);
    return res;
  }, [client]);

  const syncModels = useCallback(async () => {
    setSyncing(true);
    setError(null);
    const res = await client.syncOpenAISubModels();
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
    startSignIn,
    testConnection,
    syncModels,
    refreshConfig,
  };
}
