import { useState, useEffect } from 'react';
import { Settings, Key, Bot, ChevronRight, FolderOpen, Plug, Zap } from 'lucide-react';
import { cn } from '@/utils/cn';
import { Modal } from './Modal';
import { OpenRouterSettingsPanel } from './settings/OpenRouterSettingsPanel';
import { GroqSettingsPanel } from './settings/GroqSettingsPanel';
import { AgentSettingsPanel } from './settings/AgentSettingsPanel';
import { MCPSettingsPanel } from './settings/MCPSettingsPanel';
import type { ProviderId, SettingsTabId } from './ProviderSettingsDropdown';

const PROVIDER_TABS: { id: ProviderId | 'mcp'; label: string; icon: React.ReactNode }[] = [
  { id: 'openrouter', label: 'OpenRouter', icon: <Key className="w-4 h-4 text-cyan-400" /> },
  { id: 'groq', label: 'Groq', icon: <Zap className="w-4 h-4 text-amber-400" /> },
  { id: 'mcp', label: 'MCP', icon: <Plug className="w-4 h-4 text-cyan-400" /> },
];

interface SettingsModalProps {
  readonly visible: boolean;
  readonly onClose: () => void;
  /** Initial tab when opening. Defaults to first provider or agent. */
  readonly initialTab?: SettingsTabId | null;
}

export function SettingsModal({
  visible,
  onClose,
  initialTab = 'openrouter',
}: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<SettingsTabId>(initialTab ?? 'openrouter');
  const [providersExpanded, setProvidersExpanded] = useState(true);

  useEffect(() => {
    if (visible) {
      setActiveTab(initialTab ?? 'openrouter');
    }
  }, [visible, initialTab]);

  const renderContent = () => {
    if (activeTab === 'openrouter') {
      return (
        <OpenRouterSettingsPanel
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
          <nav className="px-2">
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
          </nav>
        </aside>

        <div className="flex-1 min-w-0 flex flex-col">{renderContent()}</div>
      </div>
    </Modal>
  );
}
