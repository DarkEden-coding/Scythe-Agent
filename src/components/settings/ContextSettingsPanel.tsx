import { useState, useEffect, useCallback } from 'react';
import { Check, Loader2 } from 'lucide-react';
import { api } from '@/api/client';
import { cn } from '@/utils/cn';

const DEFAULT_SPILL_THRESHOLD = 2000;
const DEFAULT_PREVIEW_TOKENS = 500;
const MIN_SPILL = 100;
const MAX_SPILL = 50000;
const MIN_PREVIEW = 50;
const MAX_PREVIEW = 5000;

function parseSpill(s: string): number | null {
  const n = parseInt(s, 10);
  if (Number.isNaN(n) || n < MIN_SPILL || n > MAX_SPILL) return null;
  return n;
}

function parsePreview(s: string): number | null {
  const n = parseInt(s, 10);
  if (Number.isNaN(n) || n < MIN_PREVIEW || n > MAX_PREVIEW) return null;
  return n;
}

export function ContextSettingsPanel() {
  const [spillInput, setSpillInput] = useState(String(DEFAULT_SPILL_THRESHOLD));
  const [previewInput, setPreviewInput] = useState(String(DEFAULT_PREVIEW_TOKENS));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [originalSpill, setOriginalSpill] = useState(DEFAULT_SPILL_THRESHOLD);
  const [originalPreview, setOriginalPreview] = useState(DEFAULT_PREVIEW_TOKENS);

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    const res = await api.getMemorySettings();
    if (res.ok) {
      const spill =
        typeof res.data.tool_output_token_threshold === 'number'
          ? Math.max(MIN_SPILL, Math.min(MAX_SPILL, res.data.tool_output_token_threshold))
          : DEFAULT_SPILL_THRESHOLD;
      const preview =
        typeof res.data.tool_output_preview_tokens === 'number'
          ? Math.max(MIN_PREVIEW, Math.min(MAX_PREVIEW, res.data.tool_output_preview_tokens))
          : DEFAULT_PREVIEW_TOKENS;
      setSpillInput(String(spill));
      setPreviewInput(String(preview));
      setOriginalSpill(spill);
      setOriginalPreview(preview);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const handleSave = async () => {
    setSaveError(null);
    const spill = parseSpill(spillInput);
    const preview = parsePreview(previewInput);
    if (spill === null) {
      setSaveError(
        `Spill threshold must be a number between ${MIN_SPILL} and ${MAX_SPILL}`,
      );
      return;
    }
    if (preview === null) {
      setSaveError(
        `Preview tokens must be a number between ${MIN_PREVIEW} and ${MAX_PREVIEW}`,
      );
      return;
    }
    setSaveSuccess(false);
    setSaving(true);
    const res = await api.setMemorySettings({
      toolOutputTokenThreshold: spill,
      toolOutputPreviewTokens: preview,
    });
    setSaving(false);
    if (res.ok) {
      const savedSpill =
        typeof res.data.tool_output_token_threshold === 'number'
          ? res.data.tool_output_token_threshold
          : spill;
      const savedPreview =
        typeof res.data.tool_output_preview_tokens === 'number'
          ? res.data.tool_output_preview_tokens
          : preview;
      setSpillInput(String(savedSpill));
      setPreviewInput(String(savedPreview));
      setOriginalSpill(savedSpill);
      setOriginalPreview(savedPreview);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } else {
      setSaveError(res.error ?? 'Failed to save');
    }
  };

  const spill = parseSpill(spillInput);
  const preview = parsePreview(previewInput);
  const hasChanges =
    (spill !== null && spill !== originalSpill) ||
    (preview !== null && preview !== originalPreview);
  const canSave = hasChanges && spill !== null && preview !== null;

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        <p className="text-sm text-gray-400">
          Configure when large tool outputs are saved to temp files and how much
          preview content is shown to the agent.
        </p>

        <div className="space-y-2">
          <label
            htmlFor="spill-threshold"
            className="block text-sm font-medium text-gray-300"
          >
            Tool output spill threshold (tokens)
          </label>
          <input
            id="spill-threshold"
            type="text"
            inputMode="numeric"
            value={spillInput}
            onChange={(e) => setSpillInput(e.target.value)}
            disabled={loading}
            placeholder={`${MIN_SPILL}–${MAX_SPILL}`}
            className="w-full max-w-[200px] px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200"
          />
          <p className="text-xs text-gray-500">
            When tool output exceeds this many tokens, it is saved to a file and
            a preview is shown. The agent can read the full output via read_file
            if needed.
          </p>
        </div>

        <div className="space-y-2">
          <label
            htmlFor="preview-tokens"
            className="block text-sm font-medium text-gray-300"
          >
            Tool output preview (tokens)
          </label>
          <input
            id="preview-tokens"
            type="text"
            inputMode="numeric"
            value={previewInput}
            onChange={(e) => setPreviewInput(e.target.value)}
            disabled={loading}
            placeholder={`${MIN_PREVIEW}–${MAX_PREVIEW}`}
            className="w-full max-w-[200px] px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200"
          />
          <p className="text-xs text-gray-500">
            Tokens shown (first + last) when tool output is spilled. Higher
            values give more context but use more budget.
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
            disabled={saving || loading || !canSave}
            className={cn(
              'flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-colors',
              'bg-violet-500 hover:bg-violet-600 text-white',
              (saving || loading || !canSave) && 'opacity-50 cursor-not-allowed',
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
