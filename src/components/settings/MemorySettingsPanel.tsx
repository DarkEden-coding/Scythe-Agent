import { useState, useEffect, useCallback, useMemo, ChangeEvent } from 'react';
import { Check, Loader2, Brain, Database, RefreshCw } from 'lucide-react';
import { api } from '@/api/client';
import { cn } from '@/utils/cn';
import type {
  ChatObservationSnapshot,
  ChatMemoryStateResponse,
  MemorySettings,
} from '@/api/types';

const DEFAULT_SETTINGS: MemorySettings = {
  memory_mode: 'observational',
  observer_model: null,
  reflector_model: null,
  observer_threshold: 30000,
  buffer_tokens: 6000,
  reflector_threshold: 8000,
  show_observations_in_chat: false,
};

type ThresholdInputKey = 'observer' | 'buffer' | 'reflector';
type ThresholdSettingKey = 'observer_threshold' | 'buffer_tokens' | 'reflector_threshold';

const THRESHOLD_INPUT_LABELS: Record<ThresholdInputKey, string> = {
  observer: 'Activation Threshold',
  buffer: 'Buffer Tokens',
  reflector: 'Reflector Threshold',
};

const THRESHOLD_SETTING_TO_INPUT_KEY: Record<ThresholdSettingKey, ThresholdInputKey> = {
  observer_threshold: 'observer',
  buffer_tokens: 'buffer',
  reflector_threshold: 'reflector',
};

function buildThresholdInputState(source: MemorySettings): Record<ThresholdInputKey, string> {
  return {
    observer: source.observer_threshold.toString(),
    buffer: source.buffer_tokens.toString(),
    reflector: source.reflector_threshold.toString(),
  };
}

interface MemorySettingsPanelProps {
  readonly activeChatId?: string | null;
}

interface ChatBufferChunkSnapshot {
  content: string;
  tokenCount: number;
  observedUpToMessageId: string | null;
  observedUpToTimestamp: string | null;
  currentTask: string | null;
  suggestedResponse: string | null;
}

type MemoryObservationRow = ChatObservationSnapshot & {
  source: 'stored' | 'buffered';
  observedUpToTimestamp?: string | null;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null;
}

function asBufferChunk(value: unknown): ChatBufferChunkSnapshot | null {
  const raw = asRecord(value);
  if (!raw) return null;
  const content = typeof raw.content === 'string' ? raw.content.trim() : '';
  if (!content) return null;
  return {
    content,
    tokenCount:
      typeof raw.tokenCount === 'number' && Number.isFinite(raw.tokenCount) && raw.tokenCount > 0
        ? raw.tokenCount
        : Math.max(1, Math.floor(content.length / 4)),
    observedUpToMessageId:
      typeof raw.observedUpToMessageId === 'string' ? raw.observedUpToMessageId : null,
    observedUpToTimestamp:
      typeof raw.observedUpToTimestamp === 'string' ? raw.observedUpToTimestamp : null,
    currentTask:
      typeof raw.currentTask === 'string' && raw.currentTask.trim()
        ? raw.currentTask.trim()
        : null,
    suggestedResponse:
      typeof raw.suggestedResponse === 'string' && raw.suggestedResponse.trim()
        ? raw.suggestedResponse.trim()
        : null,
  };
}

function formatTimestamp(raw: string | null | undefined): string {
  if (!raw) return 'Pending';
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? 'Pending' : parsed.toLocaleString();
}

export function MemorySettingsPanel({ activeChatId = null }: MemorySettingsPanelProps) {
  const [settings, setSettings] = useState<MemorySettings>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [original, setOriginal] = useState<MemorySettings>(DEFAULT_SETTINGS);
  const [chatMemory, setChatMemory] = useState<ChatMemoryStateResponse | null>(null);
  const [chatMemoryLoading, setChatMemoryLoading] = useState(false);
  const [chatMemoryError, setChatMemoryError] = useState<string | null>(null);
  const [thresholdInputValues, setThresholdInputValues] = useState<Record<ThresholdInputKey, string>>(
    () => buildThresholdInputState(DEFAULT_SETTINGS),
  );

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    const res = await api.getMemorySettings();
    if (res.ok) {
      const normalized: MemorySettings = {
        ...res.data,
        buffer_tokens:
          typeof res.data.buffer_tokens === 'number'
            ? res.data.buffer_tokens
            : Math.max(500, Math.floor((res.data.observer_threshold ?? 30000) * 0.2)),
      };
      setSettings(normalized);
      setOriginal(normalized);
      setThresholdInputValues(buildThresholdInputState(normalized));
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const fetchChatMemory = useCallback(async () => {
    if (!activeChatId) {
      setChatMemory(null);
      setChatMemoryError(null);
      return;
    }
    setChatMemoryLoading(true);
    setChatMemoryError(null);
    const res = await api.getMemoryState(activeChatId);
    if (res.ok) {
      setChatMemory(res.data);
    } else {
      setChatMemory(null);
      setChatMemoryError(res.error ?? 'Failed to load chat memory state');
    }
    setChatMemoryLoading(false);
  }, [activeChatId]);

  useEffect(() => {
    fetchChatMemory();
  }, [fetchChatMemory]);

  const handleThresholdInputChange = (key: ThresholdSettingKey) => (event: ChangeEvent<HTMLInputElement>) => {
    const inputKey = THRESHOLD_SETTING_TO_INPUT_KEY[key];
    const rawValue = event.target.value;
    setThresholdInputValues((prev) => ({ ...prev, [inputKey]: rawValue }));

    const parsed = parseInt(rawValue, 10);
    if (!rawValue || Number.isNaN(parsed)) {
      return;
    }

    setSettings((prev) => ({
      ...prev,
      [key]: parsed,
    }));
  };

  const getThresholdValueForSave = (key: ThresholdSettingKey) => {
    const rawValue = thresholdInputValues[THRESHOLD_SETTING_TO_INPUT_KEY[key]];
    const parsed = parseInt(rawValue, 10);
    if (rawValue && !Number.isNaN(parsed)) {
      return parsed;
    }
    return settings[key];
  };

  const hasChanges =
    settings.memory_mode !== original.memory_mode ||
    (settings.observer_model ?? '') !== (original.observer_model ?? '') ||
    (settings.reflector_model ?? '') !== (original.reflector_model ?? '') ||
    settings.observer_threshold !== original.observer_threshold ||
    settings.buffer_tokens !== original.buffer_tokens ||
    settings.reflector_threshold !== original.reflector_threshold ||
    settings.show_observations_in_chat !== original.show_observations_in_chat;

  const observationRows = useMemo<MemoryObservationRow[]>(() => {
    const storedRows: MemoryObservationRow[] = (chatMemory?.observations ?? []).map((obs) => ({
      ...obs,
      source: 'stored',
    }));

    const state = asRecord(chatMemory?.state);
    const buffer = asRecord(state?.buffer);
    const chunksRaw = Array.isArray(buffer?.chunks) ? buffer.chunks : [];
    const generation =
      typeof state?.generation === 'number'
        ? state.generation
        : storedRows[0]?.generation ?? 0;

    const bufferedRows: MemoryObservationRow[] = chunksRaw.flatMap((chunk, index) => {
      const parsed = asBufferChunk(chunk);
      if (!parsed) return [];
      const timestamp = parsed.observedUpToTimestamp ?? chatMemory?.updatedAt ?? new Date(0).toISOString();
      return [
        {
          id: `buffer-${generation}-${index}-${parsed.observedUpToMessageId ?? 'none'}-${timestamp}`,
          generation,
          tokenCount: parsed.tokenCount,
          observedUpToMessageId: parsed.observedUpToMessageId,
          currentTask: parsed.currentTask,
          suggestedResponse: parsed.suggestedResponse,
          content: parsed.content,
          timestamp,
          source: 'buffered',
          observedUpToTimestamp: parsed.observedUpToTimestamp,
        },
      ];
    });

    return [...storedRows, ...bufferedRows].sort((a, b) => {
      const left = new Date(a.timestamp).getTime();
      const right = new Date(b.timestamp).getTime();
      return (Number.isNaN(right) ? 0 : right) - (Number.isNaN(left) ? 0 : left);
    });
  }, [chatMemory]);
  const parsedState = chatMemory?.state
    ? JSON.stringify(chatMemory.state, null, 2)
    : chatMemory?.stateJson ?? '{}';

  const handleSave = async () => {
    setSaveError(null);
    setSaveSuccess(false);

    const nextObserverThreshold = getThresholdValueForSave('observer_threshold');
    const nextBufferTokens = getThresholdValueForSave('buffer_tokens');
    const nextReflectorThreshold = getThresholdValueForSave('reflector_threshold');

    const thresholdEntries = [
      ['observer_threshold', nextObserverThreshold] as const,
      ['buffer_tokens', nextBufferTokens] as const,
      ['reflector_threshold', nextReflectorThreshold] as const,
    ];

    const invalidThreshold = thresholdEntries.find(([, value]) => value === 0);
    if (invalidThreshold) {
      const label = THRESHOLD_INPUT_LABELS[
        THRESHOLD_SETTING_TO_INPUT_KEY[invalidThreshold[0]]
      ];
      setSaveError(`${label} cannot be 0000.`);
      return;
    }

    setSaving(true);
    const res = await api.setMemorySettings({
      memoryMode: settings.memory_mode,
      observerModel: settings.observer_model ?? '',
      reflectorModel: settings.reflector_model ?? '',
      observerThreshold: nextObserverThreshold,
      bufferTokens: nextBufferTokens,
      reflectorThreshold: nextReflectorThreshold,
      showObservationsInChat: settings.show_observations_in_chat,
    });
    setSaving(false);
    if (res.ok) {
      const normalized: MemorySettings = {
        ...res.data,
        buffer_tokens:
          typeof res.data.buffer_tokens === 'number'
            ? res.data.buffer_tokens
            : Math.max(500, Math.floor((res.data.observer_threshold ?? 30000) * 0.2)),
      };
      setSettings(normalized);
      setOriginal(normalized);
      setThresholdInputValues(buildThresholdInputState(normalized));
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } else {
      setSaveError(res.error ?? 'Failed to save');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-violet-400" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        <p className="text-sm text-gray-400">
          Configure how Scythe manages long conversation history. Observational Memory
          uses background AI agents to maintain a dense summary, enabling much longer
          conversations without losing context.
        </p>

        <div className="border border-gray-700/40 rounded-xl p-4 bg-gray-900/30 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-gray-200">Current Chat Memory Snapshot</p>
              <p className="text-xs text-gray-500">
                {activeChatId ? `Chat: ${activeChatId}` : 'No chat selected'}
              </p>
            </div>
            <button
              type="button"
              onClick={fetchChatMemory}
              disabled={!activeChatId || chatMemoryLoading}
              className={cn(
                'inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border',
                'bg-gray-800/60 border-gray-600/50 text-gray-200 hover:bg-gray-700/60',
                'disabled:opacity-50 disabled:cursor-not-allowed',
              )}
            >
              {chatMemoryLoading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5" />
              )}
              Refresh
            </button>
          </div>

          {!activeChatId && (
            <p className="text-xs text-gray-500">
              Open a chat first to inspect its live memory state and observations.
            </p>
          )}

          {chatMemoryError && (
            <p className="text-xs text-red-300">{chatMemoryError}</p>
          )}

          {activeChatId && !chatMemoryLoading && !chatMemoryError && (
            <div className="space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
                <div className="rounded-lg border border-gray-700/50 bg-gray-900/40 px-3 py-2">
                  <p className="text-gray-500">Strategy</p>
                  <p className="text-gray-200 mt-0.5">{chatMemory?.strategy ?? 'none'}</p>
                </div>
                <div className="rounded-lg border border-gray-700/50 bg-gray-900/40 px-3 py-2">
                  <p className="text-gray-500">Memory State</p>
                  <p className="text-gray-200 mt-0.5">{chatMemory?.hasMemoryState ? 'present' : 'empty'}</p>
                </div>
                <div className="rounded-lg border border-gray-700/50 bg-gray-900/40 px-3 py-2">
                  <p className="text-gray-500">Observations</p>
                  <p className="text-gray-200 mt-0.5">{observationRows.length}</p>
                </div>
              </div>

              {chatMemory?.updatedAt && (
                <p className="text-xs text-gray-500">
                  Updated: {new Date(chatMemory.updatedAt).toLocaleString()}
                </p>
              )}

              <div>
                <p className="text-xs font-medium text-gray-400 mb-1">Memory State JSON</p>
                <pre className="max-h-56 overflow-auto rounded-lg border border-gray-700/50 bg-black/30 p-3 text-[11px] text-gray-300 whitespace-pre-wrap break-words">
                  {parsedState}
                </pre>
              </div>

              <div>
                <p className="text-xs font-medium text-gray-400 mb-1">Observations</p>
                {observationRows.length === 0 ? (
                  <p className="text-xs text-gray-500">No observations stored for this chat yet.</p>
                ) : (
                  <div className="space-y-2 max-h-80 overflow-auto pr-1">
                    {observationRows.map((obs) => (
                      <div key={obs.id} className="rounded-lg border border-violet-500/20 bg-violet-500/5 p-3">
                        <div className="flex items-center justify-between gap-2 text-xs">
                          <span className="text-violet-300">
                            Gen {obs.generation} • {obs.tokenCount.toLocaleString()} tokens
                            {obs.source === 'buffered' ? ' • buffered' : ''}
                          </span>
                          <span className="text-gray-500">{formatTimestamp(obs.timestamp)}</span>
                        </div>
                        {obs.source === 'buffered' && (
                          <p className="text-[11px] text-gray-500 mt-1">
                            Buffered chunk {obs.observedUpToTimestamp ? `up to ${formatTimestamp(obs.observedUpToTimestamp)}` : '(pending activation)'}
                          </p>
                        )}
                        {obs.currentTask && (
                          <p className="text-xs text-gray-300 mt-2">
                            <span className="text-gray-500">Task:</span> {obs.currentTask}
                          </p>
                        )}
                        {obs.suggestedResponse && (
                          <p className="text-xs text-gray-300 mt-1">
                            <span className="text-gray-500">Hint:</span> {obs.suggestedResponse}
                          </p>
                        )}
                        <pre className="mt-2 text-[11px] text-gray-300 whitespace-pre-wrap break-words max-h-48 overflow-auto">
                          {obs.content}
                        </pre>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Memory Mode */}
        <div className="space-y-3">
          <label className="block text-sm font-medium text-gray-300">Memory Mode</label>
          <div className="space-y-2">
            <label className="flex items-start gap-3 cursor-pointer group">
              <input
                type="radio"
                name="memory_mode"
                value="observational"
                checked={settings.memory_mode === 'observational'}
                onChange={() => setSettings((s) => ({ ...s, memory_mode: 'observational' }))}
                className="mt-0.5 accent-violet-500"
              />
              <div>
                <div className="flex items-center gap-2 text-sm font-medium text-gray-200">
                  <Brain className="w-3.5 h-3.5 text-violet-400" />
                  Observational Memory
                  <span className="text-xs px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-300 border border-violet-500/30">
                    Recommended
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5">
                  Background Observer/Reflector agents maintain a structured memory log.
                  3–6× compression with full detail preservation. Falls back to Classic
                  Compaction at 95% context.
                </p>
              </div>
            </label>

            <label className="flex items-start gap-3 cursor-pointer group">
              <input
                type="radio"
                name="memory_mode"
                value="compaction"
                checked={settings.memory_mode === 'compaction'}
                onChange={() => setSettings((s) => ({ ...s, memory_mode: 'compaction' }))}
                className="mt-0.5 accent-cyan-500"
              />
              <div>
                <div className="flex items-center gap-2 text-sm font-medium text-gray-200">
                  <Database className="w-3.5 h-3.5 text-cyan-400" />
                  Classic Compaction
                </div>
                <p className="text-xs text-gray-500 mt-0.5">
                  Simple one-shot summarization when context reaches 85%. Faster but less
                  accurate for long conversations.
                </p>
              </div>
            </label>
          </div>
        </div>

        {/* OM Settings (only when observational mode is active) */}
        {settings.memory_mode === 'observational' && (
          <>
            <div className="border-t border-gray-700/30 pt-5 space-y-4">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                Observer / Reflector Models
              </p>
              <p className="text-xs text-gray-500">
                Leave blank to use the same model as the main agent. Use any model
                identifier supported by your provider (e.g.{' '}
                <code className="bg-gray-800 px-1 rounded text-violet-300">
                  google/gemini-2.5-flash
                </code>
                ).
              </p>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    Observer Model
                  </label>
                  <input
                    type="text"
                    value={settings.observer_model ?? ''}
                    onChange={(e) =>
                      setSettings((s) => ({ ...s, observer_model: e.target.value || null }))
                    }
                    placeholder="Same as main agent"
                    className={cn(
                      'w-full px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg',
                      'text-sm text-gray-200 placeholder-gray-600',
                      'focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30',
                    )}
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    Reflector Model
                  </label>
                  <input
                    type="text"
                    value={settings.reflector_model ?? ''}
                    onChange={(e) =>
                      setSettings((s) => ({ ...s, reflector_model: e.target.value || null }))
                    }
                    placeholder="Same as main agent"
                    className={cn(
                      'w-full px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg',
                      'text-sm text-gray-200 placeholder-gray-600',
                      'focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30',
                    )}
                  />
                </div>
              </div>
            </div>

            <div className="border-t border-gray-700/30 pt-5 space-y-4">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                Thresholds (tokens)
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    Activation Threshold
                  </label>
                  <input
                    type="number"
                    min={5000}
                    max={200000}
                    step={1000}
                    value={thresholdInputValues.observer}
                    onChange={handleThresholdInputChange('observer_threshold')}
                    className={cn(
                      'w-full px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg',
                      'text-sm text-gray-200',
                      'focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30',
                    )}
                  />
                  <p className="text-xs text-gray-600 mt-0.5">
                    Unobserved tokens before buffered chunks are activated
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    Buffer Tokens
                  </label>
                  <input
                    type="number"
                    min={500}
                    max={100000}
                    step={500}
                    value={thresholdInputValues.buffer}
                    onChange={handleThresholdInputChange('buffer_tokens')}
                    className={cn(
                      'w-full px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg',
                      'text-sm text-gray-200',
                      'focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30',
                    )}
                  />
                  <p className="text-xs text-gray-600 mt-0.5">
                    Async chunk size for passive observation
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    Reflector Threshold
                  </label>
                  <input
                    type="number"
                    min={5000}
                    max={200000}
                    step={1000}
                    value={thresholdInputValues.reflector}
                    onChange={handleThresholdInputChange('reflector_threshold')}
                    className={cn(
                      'w-full px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg',
                      'text-sm text-gray-200',
                      'focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30',
                    )}
                  />
                  <p className="text-xs text-gray-600 mt-0.5">Tokens before Reflector runs</p>
                </div>
              </div>
            </div>

            <div className="border-t border-gray-700/30 pt-5">
              <label className="flex items-center gap-3 cursor-pointer">
                <button
                  role="switch"
                  aria-checked={settings.show_observations_in_chat}
                  onClick={() =>
                    setSettings((s) => ({
                      ...s,
                      show_observations_in_chat: !s.show_observations_in_chat,
                    }))
                  }
                  className={cn(
                    'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
                    settings.show_observations_in_chat ? 'bg-violet-600' : 'bg-gray-700',
                  )}
                >
                  <span
                    className={cn(
                      'inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform',
                      settings.show_observations_in_chat ? 'translate-x-5' : 'translate-x-1',
                    )}
                  />
                </button>
                <div>
                  <p className="text-sm font-medium text-gray-200">Show Observations in Chat</p>
                  <p className="text-xs text-gray-500">
                    When enabled, memory observations appear as special messages in the chat
                    timeline for debugging.
                  </p>
                </div>
              </label>
            </div>
          </>
        )}

        {saveError && (
          <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-lg">
            <p className="text-sm text-red-300">{saveError}</p>
          </div>
        )}

        {saveSuccess && (
          <div className="flex items-center gap-2 px-4 py-3 bg-green-500/10 border border-green-500/20 rounded-lg">
            <Check className="w-4 h-4 text-green-400 shrink-0" />
            <p className="text-sm text-green-300">Memory settings saved</p>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            className={cn(
              'flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-colors',
              'bg-violet-600 hover:bg-violet-700 text-white',
              'disabled:opacity-50 disabled:cursor-not-allowed',
            )}
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Check className="w-4 h-4" />
                Save
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => {
              setSettings(original);
              setThresholdInputValues(buildThresholdInputState(original));
            }}
            disabled={!hasChanges}
            className={cn(
              'px-4 py-2.5 rounded-lg font-medium transition-colors border',
              'bg-gray-800/50 hover:bg-gray-700/50 text-gray-200 border-gray-600/50',
              'disabled:opacity-50 disabled:cursor-not-allowed',
            )}
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}
