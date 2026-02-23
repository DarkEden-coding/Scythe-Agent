import { useState, useRef, useEffect } from 'react';
import { Settings, ChevronDown, Key, Bot, Plug, Server } from 'lucide-react';
import { cn } from '../utils/cn';

export type ProviderId = 'openrouter' | 'groq' | 'openai-sub';

export type SettingsTabId = ProviderId | 'agent' | 'mcp' | 'memory' | 'context';

interface DropdownOption {
  id: SettingsTabId;
  label: string;
  icon?: React.ReactNode;
}

const DROPDOWN_OPTIONS: DropdownOption[] = [
  { id: 'openrouter', label: 'Providers', icon: <Key className="w-4 h-4 text-cyan-400" /> },
  { id: 'mcp', label: 'MCP', icon: <Plug className="w-4 h-4 text-cyan-400" /> },
  { id: 'agent', label: 'System Prompt', icon: <Bot className="w-4 h-4 text-cyan-400" /> },
  { id: 'memory', label: 'Backend', icon: <Server className="w-4 h-4 text-violet-400" /> },
];

interface ProviderSettingsDropdownProps {
  readonly onSelectProvider: (tab: SettingsTabId) => void;
  readonly title?: string;
}

export function ProviderSettingsDropdown({
  onSelectProvider,
  title = 'Provider settings (⌘,)',
}: ProviderSettingsDropdownProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    window.addEventListener('click', handleClickOutside);
    return () => window.removeEventListener('click', handleClickOutside);
  }, []);

  const handleSelect = (tab: SettingsTabId) => {
    setOpen(false);
    onSelectProvider(tab);
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 p-2 text-gray-500 hover:text-gray-300 hover:bg-gray-800 rounded-xl transition-colors"
        title={title}
      >
        <Settings className="w-4 h-4" />
        <ChevronDown
          className={cn('w-3 h-3 transition-transform', open && 'rotate-180')}
        />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 py-1 min-w-[180px] bg-[#1a1a24] border border-gray-700/50 rounded-lg shadow-xl z-50">
          <div className="px-3 py-2 text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-700/50 mb-1">
            Settings
          </div>
          {DROPDOWN_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              onClick={() => handleSelect(opt.id)}
              className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-200 hover:bg-gray-700/50 transition-colors"
            >
              {opt.icon}
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
