import { useState } from 'react';
import { Check, X, Loader2, RefreshCw, ExternalLink, Eye, EyeOff } from 'lucide-react';
import { useGroq } from '@/api/hooks';
import { cn } from '@/utils/cn';

interface GroqSettingsPanelProps {
  readonly footer?: React.ReactNode;
}

export function GroqSettingsPanel({ footer }: GroqSettingsPanelProps) {
  const {
    config,
    loading,
    testing,
    syncing,
    error: hookError,
    setApiKey,
    testConnection,
    syncModels,
  } = useGroq();

  const [apiKeyInput, setApiKeyInput] = useState('');
  const [apiKeyFocused, setApiKeyFocused] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const handleSave = async () => {
    if (!apiKeyInput.trim()) {
      setSaveError('Please enter an API key');
      return;
    }

    setSaveError(null);
    setSaveSuccess(false);
    const res = await setApiKey(apiKeyInput);

    if (res.ok) {
      setSaveSuccess(true);
      setApiKeyInput('');
      setTimeout(() => setSaveSuccess(false), 3000);
    } else {
      setSaveError(res.error ?? 'Failed to save API key');
    }
  };

  const handleTest = async () => {
    setTestResult(null);
    const res = await testConnection();

    if (res.ok) {
      setTestResult({
        success: res.data.success,
        message: res.data.success
          ? 'Connection successful!'
          : res.data.error ?? 'Connection failed',
      });
    } else {
      setTestResult({
        success: false,
        message: res.error ?? 'Test failed',
      });
    }

    setTimeout(() => setTestResult(null), 5000);
  };

  const isConnected = config?.connected ?? false;
  const modelCount = config?.modelCount ?? 0;
  const hasApiKey = Boolean(config?.apiKeyMasked);
  const masked = hasApiKey && !apiKeyInput && !apiKeyFocused;

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        <div className="flex items-center justify-between p-4 bg-gray-800/30 rounded-lg border border-gray-700/30">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                'w-2.5 h-2.5 rounded-full',
                isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500',
              )}
            />
            <div>
              <p className="text-sm font-medium text-gray-200">
                {isConnected ? 'Connected' : 'Not Connected'}
              </p>
              <p className="text-xs text-gray-400">
                {hasApiKey
                  ? `${modelCount} model${modelCount !== 1 ? 's' : ''} available`
                  : 'No API key configured'}
              </p>
            </div>
          </div>
          {hasApiKey && (
            <div className="text-xs font-medium text-gray-400 bg-gray-900/50 px-3 py-1.5 rounded border border-gray-700/30">
              API Already Configured
            </div>
          )}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSave();
          }}
          className="space-y-2"
        >
          <label htmlFor="groq-api-key" className="block text-sm font-medium text-gray-300">
            API Key
            <a
              href="https://console.groq.com/keys"
              target="_blank"
              rel="noopener noreferrer"
              className="ml-2 text-xs text-amber-400 hover:text-amber-300 inline-flex items-center gap-1"
            >
              Get API key
              <ExternalLink className="w-3 h-3" />
            </a>
          </label>
          <div className="relative">
            <input
              id="groq-api-key"
              type={masked ? 'text' : showApiKey ? 'text' : 'password'}
              autoComplete="off"
              value={masked ? '*'.repeat(40) : apiKeyInput}
              onFocus={() => setApiKeyFocused(true)}
              onBlur={() => setApiKeyFocused(false)}
              onChange={(e) => {
                const v = e.target.value;
                setApiKeyInput(/^\*+$/.test(v) ? '' : v);
              }}
              placeholder={hasApiKey && !masked ? undefined : 'gsk_...'}
              className="w-full px-4 py-2.5 pr-12 bg-gray-900/50 border border-gray-700/50 rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/30 font-mono text-sm"
            />
            <button
              type="button"
              onClick={() => setShowApiKey(!showApiKey)}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-gray-400 hover:text-gray-200 hover:bg-gray-700/50 rounded transition-colors"
            >
              {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-xs text-gray-400">
            Your API key is encrypted and stored securely in the local database
          </p>
        </form>

        {(saveError || hookError) && (
          <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-lg">
            <X className="w-4 h-4 text-red-400 shrink-0" />
            <p className="text-sm text-red-300">{saveError || hookError}</p>
          </div>
        )}

        {saveSuccess && (
          <div className="flex items-center gap-2 px-4 py-3 bg-green-500/10 border border-green-500/20 rounded-lg">
            <Check className="w-4 h-4 text-green-400 shrink-0" />
            <p className="text-sm text-green-300">API key saved and models synced successfully!</p>
          </div>
        )}

        {testResult && (
          <div
            className={cn(
              'flex items-center gap-2 px-4 py-3 rounded-lg border',
              testResult.success
                ? 'bg-green-500/10 border-green-500/20'
                : 'bg-red-500/10 border-red-500/20',
            )}
          >
            {testResult.success ? (
              <Check className="w-4 h-4 text-green-400 shrink-0" />
            ) : (
              <X className="w-4 h-4 text-red-400 shrink-0" />
            )}
            <p
              className={cn(
                'text-sm',
                testResult.success ? 'text-green-300' : 'text-red-300',
              )}
            >
              {testResult.message}
            </p>
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={loading || !apiKeyInput.trim()}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-colors',
              'bg-amber-500 hover:bg-amber-600 text-white',
              'disabled:opacity-50 disabled:cursor-not-allowed',
            )}
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Check className="w-4 h-4" />
                Save & Sync Models
              </>
            )}
          </button>

          <button
            onClick={handleTest}
            disabled={testing || !hasApiKey}
            className={cn(
              'px-4 py-2.5 rounded-lg font-medium transition-colors border',
              'bg-gray-800/50 hover:bg-gray-700/50 text-gray-200 border-gray-600/50',
              'disabled:opacity-50 disabled:cursor-not-allowed',
            )}
          >
            {testing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              'Test Connection'
            )}
          </button>

          <button
            onClick={() => syncModels()}
            disabled={syncing || !hasApiKey}
            className={cn(
              'p-2.5 rounded-lg transition-colors border',
              'bg-gray-800/50 hover:bg-gray-700/50 text-gray-200 border-gray-600/50',
              'disabled:opacity-50 disabled:cursor-not-allowed',
            )}
            title="Sync models"
          >
            {syncing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
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
