import { Bot, Terminal, ChevronDown } from 'lucide-react';
import { ChatTabBar } from './ChatTabBar';
import { ProviderSettingsDropdown, type ProviderId } from '@/components/ProviderSettingsDropdown';
import type { ProjectChat } from '@/types';

interface AppHeaderProps {
  readonly currentProjectChats: ProjectChat[];
  readonly activeChatId: string | null;
  readonly processingChats: Set<string>;
  readonly currentProjectId?: string;
  readonly onSwitchChat: (chatId: string) => void;
  readonly onReorderChats: (projectId: string, chatIds: string[]) => Promise<void> | void;
  readonly onOpenModelPicker: () => void;
  readonly onPrefetchSettings: () => void;
  readonly currentModel: string;
  readonly onSelectSettingsProvider: (id: ProviderId | null) => void;
  readonly projectsLoading?: boolean;
  readonly chatLoading?: boolean;
}

export function AppHeader({
  currentProjectChats,
  activeChatId,
  processingChats,
  currentProjectId = '',
  onSwitchChat,
  onReorderChats,
  onOpenModelPicker,
  onPrefetchSettings,
  currentModel,
  onSelectSettingsProvider,
  projectsLoading = false,
  chatLoading = false,
}: AppHeaderProps) {
  return (
    <header className="flex items-center justify-between gap-3 px-5 py-2.5 bg-gray-900/80 border-b border-gray-700/30 min-h-0">
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <div className="flex items-center justify-center w-8 h-8 bg-linear-to-br from-aqua-400 to-aqua-600 rounded-xl shadow-lg shadow-aqua-500/20 shrink-0">
          <Bot className="w-4.5 h-4.5 text-gray-950" />
        </div>
        <h1 className="text-sm font-semibold text-gray-200 shrink-0">Agentic Coder</h1>
        <div className="flex items-center gap-1.5 min-w-0 flex-1 overflow-hidden">
          <ChatTabBar
            chats={currentProjectChats}
            activeChatId={activeChatId}
            processingChats={processingChats}
            onSwitchChat={onSwitchChat}
            onReorderChats={onReorderChats}
            projectId={currentProjectId}
            projectsLoading={projectsLoading}
            chatLoading={chatLoading}
          />
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={onOpenModelPicker}
          onMouseEnter={onPrefetchSettings}
          className="flex items-center gap-2 px-3 py-1.5 bg-gray-800/60 rounded-xl border border-gray-700/40 shadow-sm hover:bg-gray-750 transition-colors"
          title="Change model (⌘K)"
        >
          <Terminal className="w-3.5 h-3.5 text-aqua-400" />
          <span className="text-xs text-gray-400">{currentModel}</span>
          <ChevronDown className="w-3 h-3 text-gray-500" />
        </button>

        <ProviderSettingsDropdown onSelectProvider={onSelectSettingsProvider} />
      </div>
    </header>
  );
}
