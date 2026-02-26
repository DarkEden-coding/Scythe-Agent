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
  const [subAgentModel, setSubAgentModel] = useState<string | null>(
    cached?.subAgentModel ?? null,
  );
  const [subAgentModelProvider, setSubAgentModelProvider] = useState<string | null>(
    cached?.subAgentModelProvider ?? null,
  );
  const [subAgentModelKey, setSubAgentModelKey] = useState<string | null>(
    cached?.subAgentModelKey ?? null,
  );
  const [visionPreprocessorModel, setVisionPreprocessorModel] = useState<string | null>(
    cached?.visionPreprocessorModel ?? null,
  );
  const [visionPreprocessorModelKey, setVisionPreprocessorModelKey] = useState<string | null>(
    cached?.visionPreprocessorModelKey ?? null,
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
      setSubAgentModel(res.data.subAgentModel ?? null);
      setSubAgentModelProvider(res.data.subAgentModelProvider ?? null);
      setSubAgentModelKey(res.data.subAgentModelKey ?? null);
      setVisionPreprocessorModel(res.data.visionPreprocessorModel ?? null);
      setVisionPreprocessorModelKey(res.data.visionPreprocessorModelKey ?? null);
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
        setSubAgentModel(res.data.subAgentModel ?? null);
        setSubAgentModelProvider(res.data.subAgentModelProvider ?? null);
        setSubAgentModelKey(res.data.subAgentModelKey ?? null);
        setVisionPreprocessorModel(res.data.visionPreprocessorModel ?? null);
        setVisionPreprocessorModelKey(res.data.visionPreprocessorModelKey ?? null);
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

  const changeSubAgentModel = useCallback(
    async (selection: { model: string; provider?: string; modelKey?: string } | null) => {
      const res = await client.changeSubAgentModel(
        selection === null
          ? { model: null, provider: null, modelKey: null }
          : { model: selection.model, provider: selection.provider, modelKey: selection.modelKey },
      );
      if (res.ok) {
        setSubAgentModel(res.data.subAgentModel ?? null);
        setSubAgentModelProvider(res.data.subAgentModelProvider ?? null);
        setSubAgentModelKey(res.data.subAgentModelKey ?? null);
        if (settingsCache) {
          settingsCache = {
            ...settingsCache,
            data: {
              ...settingsCache.data,
              subAgentModel: res.data.subAgentModel,
              subAgentModelProvider: res.data.subAgentModelProvider,
              subAgentModelKey: res.data.subAgentModelKey,
            },
          };
        }
      }
      return res;
    },
    [client],
  );

  const changeVisionPreprocessorModel = useCallback(
    async (selection: { model: string; provider?: string; modelKey?: string } | null) => {
      const res = await client.changeVisionPreprocessorModel(
        selection === null
          ? { model: null, provider: null, modelKey: null }
          : { model: selection.model, provider: selection.provider, modelKey: selection.modelKey },
      );
      if (res.ok) {
        setVisionPreprocessorModel(res.data.visionPreprocessorModel ?? null);
        setVisionPreprocessorModelKey(res.data.visionPreprocessorModelKey ?? null);
        if (settingsCache) {
          settingsCache = {
            ...settingsCache,
            data: {
              ...settingsCache.data,
              visionPreprocessorModel: res.data.visionPreprocessorModel,
              visionPreprocessorModelKey: res.data.visionPreprocessorModelKey,
            },
          };
        }
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

  const addAutoApproveRule = useCallback(
    async (rule: { field: AutoApproveRule['field']; value: string; enabled?: boolean }) => {
      const res = await client.addAutoApproveRule({
        field: rule.field,
        value: rule.value,
        enabled: rule.enabled ?? true,
      });
      if (res.ok) {
        setAutoApproveRules((prev) => [...prev, res.data.rule]);
      }
      return res;
    },
    [client],
  );

  const removeAutoApproveRule = useCallback(
    async (ruleId: string) => {
      const res = await client.removeAutoApproveRule(ruleId);
      if (res.ok && res.data.deleted) {
        setAutoApproveRules((prev) => prev.filter((r) => r.id !== ruleId));
      }
      return res;
    },
    [client],
  );

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
    changeSubAgentModel,
    changeVisionPreprocessorModel,
    subAgentModel,
    subAgentModelProvider,
    subAgentModelKey,
    visionPreprocessorModel,
    visionPreprocessorModelKey,
    maxParallelSubAgents: state.data?.maxParallelSubAgents ?? 4,
    subAgentMaxIterations: state.data?.subAgentMaxIterations ?? 25,
    setSubAgentSettings: useCallback(
      async (opts: { maxParallelSubAgents?: number; subAgentMaxIterations?: number }) => {
        const res = await client.setSubAgentSettings(opts);
        if (res.ok) {
          setState((s) =>
            s.data
              ? {
                  ...s,
                  data: {
                    ...s.data,
                    maxParallelSubAgents: res.data.maxParallelSubAgents ?? 4,
                    subAgentMaxIterations: res.data.subAgentMaxIterations ?? 25,
                  },
                }
              : s,
          );
        }
        return res;
      },
      [client],
    ),
    updateAutoApproveRules,
    getAutoApproveRules,
    addAutoApproveRule,
    removeAutoApproveRule,
    setSystemPrompt,
    setReasoningLevel,
    prefetchSettings,
  };
}
