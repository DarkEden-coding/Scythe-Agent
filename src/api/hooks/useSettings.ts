import { useState, useEffect, useCallback } from 'react';
import { api as defaultApi, ApiClient } from '@/api/client';
import type { ApiResponse, GetSettingsResponse, AutoApproveRule } from '@/api/types';

const SETTINGS_CACHE_TTL_MS = 5 * 60 * 1000;
let settingsCache: { data: GetSettingsResponse; fetchedAt: number } | null = null;

async function getSettingsCached(client: ApiClient): Promise<ApiResponse<GetSettingsResponse>> {
  const now = Date.now();
  if (settingsCache && now - settingsCache.fetchedAt < SETTINGS_CACHE_TTL_MS) {
    return { ok: true, data: settingsCache.data, timestamp: new Date().toISOString() };
  }
  const res = await client.getSettings();
  if (res.ok) {
    settingsCache = { data: res.data, fetchedAt: Date.now() };
  }
  return res;
}

function getSettingsCacheSnapshot(): GetSettingsResponse | null {
  if (settingsCache && Date.now() - settingsCache.fetchedAt < SETTINGS_CACHE_TTL_MS) {
    return settingsCache.data;
  }
  return null;
}

export function useSettings(client: ApiClient = defaultApi) {
  const cached = getSettingsCacheSnapshot();
  const [state, setState] = useState<{
    data: GetSettingsResponse | null;
    loading: boolean;
    error: string | null;
  }>({
    data: cached,
    loading: !cached,
    error: null,
  });
  const [currentModel, setCurrentModel] = useState(cached?.model ?? 'Claude Sonnet 4');
  const [currentModelProvider, setCurrentModelProvider] = useState<string | null>(
    cached?.modelProvider ?? null,
  );
  const [currentModelKey, setCurrentModelKey] = useState<string | null>(
    cached?.modelKey ?? null,
  );
  const [autoApproveRules, setAutoApproveRules] = useState<AutoApproveRule[]>(
    cached?.autoApproveRules ?? [],
  );

  const fetchSettings = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    const res = await getSettingsCached(client);
    if (res.ok) {
      setState({ data: res.data, loading: false, error: null });
      setCurrentModel(res.data.model);
      setCurrentModelProvider(res.data.modelProvider ?? null);
      setCurrentModelKey(res.data.modelKey ?? null);
      setAutoApproveRules(res.data.autoApproveRules);
    } else {
      setState((s) => ({
        ...s,
        loading: false,
        error: res.error ?? 'Unknown error',
      }));
    }
    return res;
  }, [client]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const prefetchSettings = useCallback(() => {
    return getSettingsCached(client).then((res) => {
      if (res.ok) {
        setState({ data: res.data, loading: false, error: null });
        setCurrentModel(res.data.model);
        setCurrentModelProvider(res.data.modelProvider ?? null);
        setCurrentModelKey(res.data.modelKey ?? null);
        setAutoApproveRules(res.data.autoApproveRules);
      }
      return res;
    });
  }, [client]);

  const setSystemPrompt = useCallback(
    async (systemPrompt: string) => {
      const res = await client.setSystemPrompt({ systemPrompt });
      if (res.ok) {
        if (settingsCache) {
          settingsCache = {
            ...settingsCache,
            data: { ...settingsCache.data, systemPrompt: res.data.systemPrompt },
          };
        }
        setState((s) =>
          s.data ? { ...s, data: { ...s.data, systemPrompt: res.data.systemPrompt } } : s,
        );
      }
      return res;
    },
    [client],
  );

  const setReasoningLevel = useCallback(
    async (reasoningLevel: string) => {
      const res = await client.setReasoningLevel({ reasoningLevel });
      if (res.ok) {
        if (settingsCache) {
          settingsCache = {
            ...settingsCache,
            data: { ...settingsCache.data, reasoningLevel: res.data.reasoningLevel },
          };
        }
        setState((s) =>
          s.data
            ? {
                ...s,
                data: { ...s.data, reasoningLevel: res.data.reasoningLevel },
              }
            : s,
        );
      }
      return res;
    },
    [client],
  );

  const changeModel = useCallback(
    async (selection: { model: string; provider?: string; modelKey?: string }) => {
      const res = await client.changeModel(selection);
      if (res.ok) {
        setCurrentModel(res.data.model);
        const parsedProvider =
          selection.provider ??
          (selection.modelKey?.includes('::')
            ? selection.modelKey.split('::', 1)[0]
            : null);
        setCurrentModelProvider(parsedProvider);
        setCurrentModelKey(selection.modelKey ?? null);
        if (settingsCache) {
          settingsCache = {
            ...settingsCache,
            data: {
              ...settingsCache.data,
              model: res.data.model,
              modelProvider: parsedProvider,
              modelKey: selection.modelKey ?? null,
            },
          };
        }
      }
      return res;
    },
    [client],
  );

  const updateAutoApproveRules = useCallback(
    async (rules: Omit<AutoApproveRule, 'id' | 'createdAt'>[]) => {
      const res = await client.setAutoApproveRules({ rules });
      if (res.ok) {
        setAutoApproveRules(res.data.rules);
      }
      return res;
    },
    [client],
  );

  const getAutoApproveRules = useCallback(async () => {
    const res = await client.getAutoApproveRules();
    if (res.ok) {
      setAutoApproveRules(res.data.rules);
    }
    return res;
  }, [client]);

  return {
    settings: state.data,
    loading: state.loading,
    error: state.error,
    currentModel,
    currentModelProvider,
    currentModelKey,
    availableModels: state.data?.availableModels ?? [],
    modelsByProvider: state.data?.modelsByProvider ?? {},
    modelMetadata: state.data?.modelMetadata ?? {},
    modelMetadataByKey: state.data?.modelMetadataByKey ?? {},
    contextLimit: state.data?.contextLimit ?? 128_000,
    reasoningLevel: state.data?.reasoningLevel ?? 'medium',
    systemPrompt: state.data?.systemPrompt ?? '',
    autoApproveRules,
    changeModel,
    updateAutoApproveRules,
    getAutoApproveRules,
    setSystemPrompt,
    setReasoningLevel,
    prefetchSettings,
  };
}
