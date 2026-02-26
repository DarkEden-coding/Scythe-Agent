import { useState } from 'react';
import { Check, Loader2, Plus, Trash2 } from 'lucide-react';
import { useSettings } from '@/api/hooks';
import type { AutoApproveRule } from '@/api';
import { cn } from '@/utils/cn';

function getPlaceholderForField(field: AutoApproveRule['field']): string {
  if (field === 'tool') return 'e.g. read_file';
  if (field === 'extension') return 'e.g. .md';
  if (field === 'pattern') return 'substring to match';
  return 'path or pattern';
}

const FIELD_OPTIONS: { value: AutoApproveRule['field']; label: string }[] = [
  { value: 'tool', label: 'Tool' },
  { value: 'path', label: 'Path' },
  { value: 'extension', label: 'Extension' },
  { value: 'directory', label: 'Directory' },
  { value: 'pattern', label: 'Pattern' },
];

export function AutoApproveSettingsPanel() {
  const {
    autoApproveRules,
    addAutoApproveRule,
    removeAutoApproveRule,
    updateAutoApproveRules,
    loading: settingsLoading,
  } = useSettings();
  const [newField, setNewField] = useState<AutoApproveRule['field']>('tool');
  const [newValue, setNewValue] = useState('');
  const [adding, setAdding] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAdd = async () => {
    const trimmed = newValue.trim();
    if (!trimmed) {
      setError('Value is required');
      return;
    }
    setError(null);
    setAdding(true);
    const res = await addAutoApproveRule({
      field: newField,
      value: trimmed,
      enabled: true,
    });
    setAdding(false);
    if (res.ok) {
      setNewValue('');
    } else {
      setError(res.error ?? 'Failed to add rule');
    }
  };

  const handleRemove = async (rule: AutoApproveRule) => {
    setRemovingId(rule.id);
    setError(null);
    const res = await removeAutoApproveRule(rule.id);
    setRemovingId(null);
    if (!res.ok) {
      setError(res.error ?? 'Failed to remove rule');
    }
  };

  const handleToggleEnabled = async (rule: AutoApproveRule) => {
    const updated = autoApproveRules.map((r) =>
      r.id === rule.id ? { ...r, enabled: !r.enabled } : r,
    );
    const res = await updateAutoApproveRules(
      updated.map((r) => ({ field: r.field, value: r.value, enabled: r.enabled })),
    );
    if (!res.ok) {
      setError(res.error ?? 'Failed to update rule');
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        <p className="text-sm text-gray-400">
          Auto-approve rules let the agent run matching tool calls without asking for confirmation.
          Match by tool name, file path, extension, directory, or a pattern in the input.
        </p>

        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-300">Add rule</h3>
          <div className="flex flex-wrap gap-2 items-end">
            <div>
              <label htmlFor="rule-field" className="block text-xs text-gray-500 mb-1">
                Field
              </label>
              <select
                id="rule-field"
                value={newField}
                onChange={(e) => setNewField(e.target.value as AutoApproveRule['field'])}
                className="px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-sm text-gray-200"
              >
                {FIELD_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-1 min-w-[160px]">
              <label htmlFor="rule-value" className="block text-xs text-gray-500 mb-1">
                Value
              </label>
              <input
                id="rule-value"
                type="text"
                value={newValue}
                onChange={(e) => {
                  setNewValue(e.target.value);
                  setError(null);
                }}
                placeholder={getPlaceholderForField(newField)}
                className="w-full px-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-sm text-gray-200"
              />
            </div>
            <button
              type="button"
              onClick={handleAdd}
              disabled={adding || settingsLoading || !newValue.trim()}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium',
                'bg-violet-500 hover:bg-violet-600 text-white',
                (adding || settingsLoading || !newValue.trim()) && 'opacity-50 cursor-not-allowed',
              )}
            >
              {adding ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              Add
            </button>
          </div>
        </div>

        <hr className="border-gray-700/50" />

        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-300">Rules</h3>
          {error && (
            <div className="px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-lg">
              <p className="text-sm text-red-300">{error}</p>
            </div>
          )}
          {autoApproveRules.length === 0 ? (
            <p className="text-sm text-gray-500 py-4">No auto-approve rules yet.</p>
          ) : (
            <ul className="space-y-2">
              {autoApproveRules.map((rule) => (
                <li
                  key={rule.id}
                  className={cn(
                    'flex items-center justify-between gap-4 px-4 py-3 rounded-lg border',
                    rule.enabled
                      ? 'bg-violet-500/5 border-violet-500/20'
                      : 'bg-gray-800/30 border-gray-700/30 opacity-60',
                  )}
                >
                  <button
                    type="button"
                    onClick={() => handleToggleEnabled(rule)}
                    className="flex items-center gap-3 flex-1 min-w-0 text-left"
                  >
                    {rule.enabled ? (
                      <Check className="w-4 h-4 text-violet-400 shrink-0" />
                    ) : (
                      <span className="w-4 h-4 rounded border border-gray-600 shrink-0" />
                    )}
                    <span className="font-mono text-xs text-amber-200/90 shrink-0">
                      {rule.field}
                    </span>
                    <span className="font-mono text-sm text-gray-300 truncate">{rule.value}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleRemove(rule)}
                    disabled={removingId === rule.id}
                    className="p-2 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors disabled:opacity-50"
                    title="Remove rule"
                  >
                    {removingId === rule.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
