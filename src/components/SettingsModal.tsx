import { useState, useEffect } from 'react';
import { Settings, Key, Bot, ChevronRight, ChevronDown, FolderOpen, Plug, Zap, Sparkles, Server, Brain, Layers, ShieldCheck } from 'lucide-react';
import { cn } from '@/utils/cn';
import { Modal } from './Modal';
import { OpenRouterSettingsPanel } from './settings/OpenRouterSettingsPanel';
import { GroqSettingsPanel } from './settings/GroqSettingsPanel';
import { OpenAISubSettingsPanel } from './settings/OpenAISubSettingsPanel';
import { ApiKeysSettingsPanel } from './settings/ApiKeysSettingsPanel';
import { AgentSettingsPanel } from './settings/AgentSettingsPanel';
import { MCPSettingsPanel } from './settings/MCPSettingsPanel';
import { MemorySettingsPanel } from './settings/MemorySettingsPanel';
import { ContextSettingsPanel } from './settings/ContextSettingsPanel';
import { AutoApproveSettingsPanel } from './settings/AutoApproveSettingsPanel';
import type { ProviderId, SettingsTabId } from './ProviderSettingsDropdown';

const PROVIDER_TABS: { id: ProviderId; label: string; icon: React.ReactNode }[] = [
  { id: 'openrouter', label: 'OpenRouter', icon: <Key className="w-4 h-4 text-cyan-400" /> },
  { id: 'groq', label: 'Groq', icon: <Zap className="w-4 h-4 text-amber-400" /> },
  { id: 'openai-sub', label: 'OpenAI Sub', icon: <Sparkles className="w-4 h-4 text-emerald-400" /> },
];

interface SettingsModalProps {
  readonly visible: boolean;
  readonly onClose: () => void;
  /** Initial tab when opening. Defaults to first provider or agent. */
  readonly initialTab?: SettingsTabId | null;
  readonly activeChatId?: string | null;
  readonly onProviderModelsChanged?: () => void;
}

export function SettingsModal({
  visible,
  onClose,
  initialTab = 'openrouter',
  activeChatId = null,
  onProviderModelsChanged,
}: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<SettingsTabId>(initialTab ?? 'openrouter');
  const [providersExpanded, setProvidersExpanded] = useState(true);
  const [backendExpanded, setBackendExpanded] = useState(true);

  useEffect(() => {
    if (visible) {
      const tab = initialTab ?? 'openrouter';
      setActiveTab(tab);
      if (tab === 'memory' || tab === 'context' || tab === 'api-keys' || tab === 'auto-approve') {
        setBackendExpanded(true);
      }
    }
  }, [visible, initialTab]);

  const renderContent = () => {
    if (activeTab === 'openrouter') {
      return (
        <OpenRouterSettingsPanel
          onModelsSynced={onProviderModelsChanged}
          footer={
            <p className="text-xs text-gray-400">
              Need help?{' '}
              <a
                href="https://openrouter.ai/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="text-cyan-400 hover:text-cyan-300 inline-flex items-center gap-1"
              >
                Read the OpenRouter docs
              </a>
            </p>
          }
        />
      );
    }
    if (activeTab === 'groq') {
      return (
        <GroqSettingsPanel
          onModelsSynced={onProviderModelsChanged}
          footer={
            <p className="text-xs text-gray-400">
              Need help?{' '}
              <a
                href="https://console.groq.com/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="text-amber-400 hover:text-amber-300 inline-flex items-center gap-1"
              >
                Read the Groq docs
              </a>
            </p>
          }
        />
      );
    }
    if (activeTab === 'openai-sub') {
      return (
        <OpenAISubSettingsPanel
          onModelsSynced={onProviderModelsChanged}
          footer={
            <p className="text-xs text-gray-400">
              Uses your ChatGPT Plus/Pro/Team subscription via OAuth. No API key needed.
            </p>
          }
        />
      );
    }
    if (activeTab === 'mcp') {
      return (
        <MCPSettingsPanel
          footer={
            <p className="text-xs text-gray-400">
              MCP servers provide tools to the agent. Use stdio (npx/uvx) for local or http for
              remote servers, then refresh to discover tools.
            </p>
          }
        />
      );
    }
    if (activeTab === 'agent') {
      return <AgentSettingsPanel />;
    }
    if (activeTab === 'memory') {
      return <MemorySettingsPanel activeChatId={activeChatId} />;
    }
    if (activeTab === 'context') {
      return <ContextSettingsPanel />;
    }
    if (activeTab === 'api-keys') {
      return (
        <ApiKeysSettingsPanel
          footer={
            <p className="text-xs text-gray-400">
              API keys for non-LLM services (e.g. Brave Search). LLM providers (OpenRouter, Groq)
              are configured under Providers.
            </p>
          }
        />
      );
    }
    if (activeTab === 'auto-approve') {
      return <AutoApproveSettingsPanel />;
    }
    return null;
  };

  return (
    <Modal
      visible={visible}
      onClose={onClose}
      title="Settings"
      subtitle="Configure providers and agent behavior"
      icon={<Settings className="w-5 h-5 text-cyan-400" />}
      maxWidth="max-w-3xl"
      maxHeight="max-h-[85vh]"
      panelClassName="flex"
    >
      <div className="flex flex-1 min-h-0">
        <aside className="w-52 shrink-0 border-r border-gray-700/50 flex flex-col py-2">
          <div className="px-3 py-2">
            <button
              onClick={() => setProvidersExpanded(!providersExpanded)}
              className="flex items-center gap-2 w-full text-left text-xs font-medium text-gray-500 uppercase tracking-wider hover:text-gray-400"
            >
              {providersExpanded ? (
                <FolderOpen className="w-4 h-4" />
              ) : (
                <ChevronRight className="w-4 h-4" />
              )}
              Providers
            </button>
          </div>
          {providersExpanded && (
            <nav className="px-2 space-y-0.5">
              {PROVIDER_TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                    activeTab === tab.id
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                      : 'text-gray-400 hover:bg-gray-800/50 hover:text-gray-200',
                  )}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </nav>
          )}

          <div className="mt-4 px-3 py-2 border-t border-gray-700/30">
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
              Agent
            </span>
          </div>
          <nav className="px-2 space-y-0.5">
            <button
              onClick={() => setActiveTab('mcp')}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                activeTab === 'mcp'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                  : 'text-gray-400 hover:bg-gray-800/50 hover:text-gray-200',
              )}
            >
              <Plug className="w-4 h-4" />
              MCP
            </button>
            <button
              onClick={() => setActiveTab('agent')}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                activeTab === 'agent'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                  : 'text-gray-400 hover:bg-gray-800/50 hover:text-gray-200',
              )}
            >
              <Bot className="w-4 h-4" />
              System Prompt
            </button>
            <div
              className={cn(
                'mt-2 overflow-hidden rounded-lg border transition-all',
                backendExpanded
                  ? 'border-violet-500/20 bg-violet-500/5'
                  : 'border-gray-700/30 bg-gray-800/30',
              )}
            >
              <button
                onClick={() => setBackendExpanded(!backendExpanded)}
                className={cn(
                  'flex items-center gap-2 w-full text-left px-3 hover:bg-gray-800/30 transition-colors',
                  backendExpanded ? 'py-2 rounded-t-lg' : 'py-1.5 rounded-lg',
                )}
              >
                {backendExpanded ? (
                  <ChevronDown className="w-3.5 h-3.5 text-gray-500 shrink-0" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5 text-gray-500 shrink-0" />
                )}
                <Server className="w-4 h-4 text-violet-400 shrink-0" />
                <span className="text-xs font-medium text-gray-300 uppercase tracking-wider truncate">
                  Backend
                </span>
              </button>
              {backendExpanded && (
                <div className="border-t border-gray-700/30 pb-1 pt-0.5">
                  <button
                    onClick={() => setActiveTab('memory')}
                    className={cn(
                      'w-full flex items-center gap-3 pl-6 pr-3 py-2 text-sm transition-colors',
                      activeTab === 'memory'
                        ? 'bg-violet-500/20 text-violet-300 border-l-2 border-l-violet-500/50'
                        : 'text-gray-400 hover:bg-gray-800/50 hover:text-gray-200 border-l-2 border-l-transparent',
                    )}
                  >
                    <Brain className="w-4 h-4 shrink-0" />
                    Memory
                  </button>
                  <button
                    onClick={() => setActiveTab('context')}
                    className={cn(
                      'w-full flex items-center gap-3 pl-6 pr-3 py-2 text-sm transition-colors',
                      activeTab === 'context'
                        ? 'bg-violet-500/20 text-violet-300 border-l-2 border-l-violet-500/50'
                        : 'text-gray-400 hover:bg-gray-800/50 hover:text-gray-200 border-l-2 border-l-transparent',
                    )}
                  >
                    <Layers className="w-4 h-4 shrink-0" />
                    Context
                  </button>
                  <button
                    onClick={() => setActiveTab('api-keys')}
                    className={cn(
                      'w-full flex items-center gap-3 pl-6 pr-3 py-2 text-sm transition-colors',
                      activeTab === 'api-keys'
                        ? 'bg-violet-500/20 text-violet-300 border-l-2 border-l-violet-500/50'
                        : 'text-gray-400 hover:bg-gray-800/50 hover:text-gray-200 border-l-2 border-l-transparent',
                    )}
                  >
                    <Key className="w-4 h-4 shrink-0" />
                    API Keys
                  </button>
                  <button
                    onClick={() => setActiveTab('auto-approve')}
                    className={cn(
                      'w-full flex items-center gap-3 pl-6 pr-3 py-2 text-sm transition-colors',
                      activeTab === 'auto-approve'
                        ? 'bg-violet-500/20 text-violet-300 border-l-2 border-l-violet-500/50'
                        : 'text-gray-400 hover:bg-gray-800/50 hover:text-gray-200 border-l-2 border-l-transparent',
                    )}
                  >
                    <ShieldCheck className="w-4 h-4 shrink-0" />
                    Auto-approve
                  </button>
                </div>
              )}
            </div>
          </nav>
        </aside>

        <div className="flex-1 min-w-0 flex flex-col">{renderContent()}</div>
      </div>
    </Modal>
  );
}
