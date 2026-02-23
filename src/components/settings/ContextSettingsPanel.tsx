import { useState, useEffect, useCallback } from 'react';
import { Check, Loader2 } from 'lucide-react';
import { api } from '@/api/client';
import { cn } from '@/utils/cn';

const DEFAULT_OVERFLOW_THRESHOLD = 0.95;
const MIN = 0.01;
const MAX = 1;
const STEP = 0.01;

export function ContextSettingsPanel() {
  const [overflowThreshold, setOverflowThreshold] = useState(DEFAULT_OVERFLOW_THRESHOLD);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [original, setOriginal] = useState(DEFAULT_OVERFLOW_THRESHOLD);

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    const res = await api.getMemorySettings();
    if (res.ok) {
      const val =
        typeof res.data.overflow_threshold === 'number'
          ? Math.max(MIN, Math.min(MAX, res.data.overflow_threshold))
          : DEFAULT_OVERFLOW_THRESHOLD;
      setOverflowThreshold(val);
      setOriginal(val);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const handleSave = async () => {
    setSaveError(null);
    setSaveSuccess(false);
    setSaving(true);
    const res = await api.setMemorySettings({ overflowThreshold: overflowThreshold });
    setSaving(false);
    if (res.ok) {
      const val =
        typeof res.data.overflow_threshold === 'number' ? res.data.overflow_threshold : overflowThreshold;
      setOverflowThreshold(val);
      setOriginal(val);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } else {
      setSaveError(res.error ?? 'Failed to save');
    }
  };

  const hasChanges = Math.abs(overflowThreshold - original) > 0.001;
  const pct = Math.round(overflowThreshold * 100);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        <p className="text-sm text-gray-400">
          When the context fills past this fraction of the model's limit, older messages are
          summarized to reclaim space. Higher values delay compaction until the context is fuller.
        </p>

        <label htmlFor="overflow-threshold" className="block text-sm font-medium text-gray-300">
          Overflow threshold
        </label>
        <div className="flex items-center gap-4">
          <input
            id="overflow-threshold"
            type="range"
            min={MIN}
            max={MAX}
            step={STEP}
            value={overflowThreshold}
            onChange={(e) => setOverflowThreshold(parseFloat(e.target.value))}
            disabled={loading}
            className="w-full max-w-[200px] px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200"
          />
          <span className="w-12 text-sm font-mono text-gray-200">{pct}%</span>
        </div>

        <div className="space-y-2">
          <label htmlFor="overflow-threshold" className="block text-sm font-medium text-gray-300">
            Overflow token threshold
          </label>
          <div className="flex items-center gap-4">
            <input
              id="overflow-threshold"
              type="range"
              min={0.01}
              max={1}
              step={0.01}
              value={overflowThreshold}
              onChange={(e) => setOverflowThreshold(Number.parseFloat(e.target.value))}
              disabled={loading}
              className="flex-1 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-violet-500"
            />
            <span className="w-12 text-sm font-mono text-gray-200">{pct}%</span>
          </div>
          <p className="text-xs text-gray-500">
            When context fills past this fraction of the model limit, older messages are summarized.
          </p>
        </div>

        <div className="space-y-2">
          <label htmlFor="spill-threshold" className="block text-sm font-medium text-gray-300">
            Tool output spill threshold (tokens)
          </label>
          <input
            id="spill-threshold"
            type="number"
            min={1}
            value={spillThreshold}
            onChange={(e) => setSpillThreshold(parseInt(e.target.value, 10) || 10000)}
            disabled={loading}
            className="flex-1 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-violet-500"
          />
          <p className="text-xs text-gray-500">
            When tool output exceeds this many tokens, it is saved to a file and a preview is shown.
          </p>
        </div>
        <p className="text-xs text-gray-500">
          {pct}% of context limit triggers summarization (e.g. 95% of 128k ≈ 122k tokens)
        </p>

        <div className="space-y-2">
          <label htmlFor="preview-tokens" className="block text-sm font-medium text-gray-300">
            Tool output preview (tokens)
          </label>
          <input
            id="preview-tokens"
            type="number"
            min={1}
            value={previewTokens}
            onChange={(e) => setPreviewTokens(parseInt(e.target.value, 10) || 1000)}
            disabled={loading}
            className="w-full max-w-[200px] px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200"
          />
          <p className="text-xs text-gray-500">
            Tokens shown (first + last half) when tool output is spilled.
          </p>
        </div>

        {saveError && (
          <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-lg">
            <p className="text-sm text-red-300">{saveError}</p>
          </div>
        )}

        {saveSuccess && (
          <div className="flex items-center gap-2 px-4 py-3 bg-green-500/10 border border-green-500/20 rounded-lg">
            <Check className="w-4 h-4 text-green-400 shrink-0" />
            <p className="text-sm text-green-300">Context settings saved</p>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={handleSave}
            disabled={saving || loading || !hasChanges}
            className={cn(
              'flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-colors',
              'bg-violet-500 hover:bg-violet-600 text-white',
              (saving || loading || !hasChanges) && 'opacity-50 cursor-not-allowed',
            )}
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Check className="w-4 h-4" />
            )}
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
