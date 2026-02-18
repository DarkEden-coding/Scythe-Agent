import { useState, useEffect } from 'react';
import { Check, Loader2 } from 'lucide-react';
import { useSettings } from '@/api/hooks';
import { cn } from '@/utils/cn';

interface AgentSettingsPanelProps {
  readonly footer?: React.ReactNode;
}

export function AgentSettingsPanel({ footer }: AgentSettingsPanelProps) {
  const { systemPrompt, setSystemPrompt, loading: settingsLoading } = useSettings();
  const [value, setValue] = useState(systemPrompt);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    setValue(systemPrompt);
  }, [systemPrompt]);

  const handleSave = async () => {
    setSaveError(null);
    setSaveSuccess(false);
    setSaving(true);
    const res = await setSystemPrompt(value);
    setSaving(false);
    if (res.ok) {
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } else {
      setSaveError(res.error ?? 'Failed to save');
    }
  };

  const hasChanges = value !== systemPrompt;

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        <p className="text-sm text-gray-400">
          Customize the system prompt sent to the model at the start of each conversation.
        </p>

        <label htmlFor="system-prompt" className="block text-sm font-medium text-gray-300">
          System Prompt
        </label>
        <textarea
          id="system-prompt"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Enter custom system prompt..."
          rows={14}
          className={cn(
            'w-full px-4 py-3 bg-gray-900/50 border border-gray-700/50 rounded-lg',
            'text-gray-200 placeholder-gray-500 font-mono text-sm',
            'focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30',
            'resize-y min-h-[200px]',
          )}
        />

        {saveError && (
          <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-lg">
            <p className="text-sm text-red-300">{saveError}</p>
          </div>
        )}

        {saveSuccess && (
          <div className="flex items-center gap-2 px-4 py-3 bg-green-500/10 border border-green-500/20 rounded-lg">
            <Check className="w-4 h-4 text-green-400 shrink-0" />
            <p className="text-sm text-green-300">System prompt saved</p>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={handleSave}
            disabled={saving || settingsLoading || !hasChanges}
            className={cn(
              'flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-colors',
              'bg-cyan-500 hover:bg-cyan-600 text-white',
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
            onClick={() => setValue(systemPrompt)}
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

      {footer && (
        <div className="shrink-0 px-6 py-4 border-t border-gray-700/50 bg-gray-800/20">
          {footer}
        </div>
      )}
    </div>
  );
}
