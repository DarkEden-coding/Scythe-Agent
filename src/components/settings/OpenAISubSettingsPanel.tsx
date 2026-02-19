import { useState, useEffect } from 'react';
import { Check, X, Loader2, RefreshCw, LogIn } from 'lucide-react';
import { useOpenAISub } from '@/api/hooks';
import { cn } from '@/utils/cn';

interface OpenAISubSettingsPanelProps {
  readonly footer?: React.ReactNode;
}

export function OpenAISubSettingsPanel({ footer }: OpenAISubSettingsPanelProps) {
  const {
    config,
    loading,
    testing,
    syncing,
    error: hookError,
    startSignIn,
    testConnection,
    syncModels,
    refreshConfig,
  } = useOpenAISub();

  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get('openai-sub');
    if (status) {
      refreshConfig();
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [refreshConfig]);

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
                {isConnected ? 'Signed in' : 'Not signed in'}
              </p>
              <p className="text-xs text-gray-400">
                {isConnected
                  ? `Uses your ChatGPT Plus/Pro subscription • ${modelCount} model${modelCount !== 1 ? 's' : ''} available`
                  : 'Sign in to use your OpenAI subscription'}
              </p>
            </div>
          </div>
          {isConnected && (
            <div className="text-xs font-medium text-gray-400 bg-gray-900/50 px-3 py-1.5 rounded border border-gray-700/30">
              OAuth Connected
            </div>
          )}
        </div>

        {!isConnected && (
          <div className="space-y-2">
            <p className="text-sm text-gray-300">
              Sign in with your OpenAI account to use ChatGPT Plus/Pro/Team credits instead of API
              keys.
            </p>
            <button
              onClick={() => startSignIn()}
              disabled={loading}
              className={cn(
                'w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-colors',
                'bg-emerald-600 hover:bg-emerald-500 text-white',
                'disabled:opacity-50 disabled:cursor-not-allowed',
              )}
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Opening sign-in...
                </>
              ) : (
                <>
                  <LogIn className="w-4 h-4" />
                  Sign in with OpenAI
                </>
              )}
            </button>
            <p className="text-xs text-gray-500">
              A browser window will open. Sign in and you&apos;ll be redirected back.
            </p>
          </div>
        )}

        {(hookError || testResult) && (
          <div
            className={cn(
              'flex items-center gap-2 px-4 py-3 rounded-lg border',
              (testResult?.success ?? false)
                ? 'bg-green-500/10 border-green-500/20'
                : 'bg-red-500/10 border-red-500/20',
            )}
          >
            {testResult?.success ? (
              <Check className="w-4 h-4 text-green-400 shrink-0" />
            ) : (
              <X className="w-4 h-4 text-red-400 shrink-0" />
            )}
            <p
              className={cn(
                'text-sm',
                testResult?.success ? 'text-green-300' : 'text-red-300',
              )}
            >
              {testResult?.message ?? hookError}
            </p>
          </div>
        )}

        {isConnected && (
          <div className="flex items-center gap-3">
            <button
              onClick={handleTest}
              disabled={testing}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-colors border',
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
              disabled={syncing}
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
        )}
      </div>

      {footer && (
        <div className="shrink-0 px-6 py-4 border-t border-gray-700/50 bg-gray-800/20">
          {footer}
        </div>
      )}
    </div>
  );
}
