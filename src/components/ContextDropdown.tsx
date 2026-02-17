import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { FileCode, MessageSquare, Terminal, FileText, Sparkles, X, ChevronDown, Brain } from 'lucide-react';
import { ContextItem } from '../types';
import { cn } from '../utils/cn';

interface ContextDropdownProps {
  contextItems: ContextItem[];
  maxTokens: number;
  onSummarize: () => void;
  onRemoveItem: (itemId: string) => void;
}

const typeIcons: Record<string, React.ReactNode> = {
  file: <FileCode className="w-3 h-3" />,
  conversation: <MessageSquare className="w-3 h-3" />,
  tool_output: <Terminal className="w-3 h-3" />,
  summary: <FileText className="w-3 h-3" />,
};

const typeColors: Record<string, string> = {
  file: 'text-cyan-300 bg-cyan-500/10 border border-cyan-500/20',
  conversation: 'text-aqua-300 bg-aqua-500/10 border border-aqua-500/20',
  tool_output: 'text-teal-300 bg-teal-500/10 border border-teal-500/20',
  summary: 'text-amber-300 bg-amber-500/10 border border-amber-500/20',
};

function DonutChart({ used, max }: { used: number; max: number }) {
  const percentage = Math.min((used / max) * 100, 100);
  const radius = 32;
  const strokeWidth = 7;
  const normalizedRadius = radius - strokeWidth / 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  const getColor = () => {
    if (percentage > 90) return '#ef4444';
    if (percentage > 70) return '#f59e0b';
    return '#22d3d8';
  };

  return (
    <div className="relative flex items-center justify-center">
      <svg width={radius * 2} height={radius * 2} className="-rotate-90">
        {/* Background circle */}
        <circle
          stroke="#2a2a3a"
          fill="transparent"
          strokeWidth={strokeWidth}
          r={normalizedRadius}
          cx={radius}
          cy={radius}
        />
        {/* Progress circle */}
        <circle
          stroke={getColor()}
          fill="transparent"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={strokeDashoffset}
          r={normalizedRadius}
          cx={radius}
          cy={radius}
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[10px] font-bold text-gray-200">{Math.round(percentage)}%</span>
      </div>
    </div>
  );
}

export function ContextDropdown({
  contextItems,
  maxTokens,
  onSummarize,
  onRemoveItem,
}: ContextDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const totalTokens = contextItems.reduce((sum, item) => sum + item.tokens, 0);
  const usagePercentage = Math.min((totalTokens / maxTokens) * 100, 100);

  const getUsageColor = () => {
    if (usagePercentage > 90) return 'text-red-400';
    if (usagePercentage > 70) return 'text-amber-400';
    return 'text-aqua-400';
  };

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      if (
        triggerRef.current?.contains(target) ||
        dropdownRef.current?.contains(target)
      ) {
        return;
      }
      setIsOpen(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (!isOpen || !triggerRef.current) return;
    const updatePosition = () => {
      if (!triggerRef.current) return;
      const rect = triggerRef.current.getBoundingClientRect();
      setPosition({ top: rect.bottom + 8, left: rect.left });
    };
    updatePosition();
    window.addEventListener('scroll', updatePosition, true);
    window.addEventListener('resize', updatePosition);
    return () => {
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
    };
  }, [isOpen]);

  // Group items by type for the legend
  const groupedByType = contextItems.reduce<Record<string, { count: number; tokens: number }>>((acc, item) => {
    if (!acc[item.type]) acc[item.type] = { count: 0, tokens: 0 };
    acc[item.type].count++;
    acc[item.type].tokens += item.tokens;
    return acc;
  }, {});

  const typeLabels: Record<string, string> = {
    file: 'Files',
    conversation: 'Conversation',
    tool_output: 'Tool Outputs',
    summary: 'Summaries',
  };

  const dropdownPanel = isOpen && (
    <div
      ref={dropdownRef}
      className="fixed z-50 min-w-[380px] animate-dropdown"
      style={{ top: position.top, left: position.left }}
    >
      <div className="bg-gray-850 border border-gray-700/60 rounded-2xl shadow-2xl shadow-black/40 overflow-hidden">
        {/* Header with chart */}
        <div className="p-4 border-b border-gray-700/40">
          <div className="flex items-start gap-4">
            <DonutChart used={totalTokens} max={maxTokens} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-gray-300">Context Window</span>
                <button
                  onClick={onSummarize}
                  className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium text-aqua-400 hover:text-aqua-300 bg-aqua-500/10 hover:bg-aqua-500/15 rounded-md border border-aqua-500/20 transition-colors"
                >
                  <Sparkles className="w-2.5 h-2.5" />
                  Summarize
                </button>
              </div>
              {/* Type breakdown */}
              <div className="space-y-1">
                {Object.entries(groupedByType).map(([type, data]) => (
                  <div key={type} className="flex items-center justify-between text-[10px]">
                    <div className="flex items-center gap-1.5">
                      <span className={cn(
                        'w-1.5 h-1.5 rounded-full',
                        type === 'file' && 'bg-cyan-400',
                        type === 'conversation' && 'bg-aqua-400',
                        type === 'tool_output' && 'bg-teal-400',
                        type === 'summary' && 'bg-amber-400',
                      )} />
                      <span className="text-gray-400">{typeLabels[type]}</span>
                      <span className="text-gray-600">({data.count})</span>
                    </div>
                    <span className="text-gray-500 font-mono">{data.tokens.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Context Items */}
        <div className="p-3 max-h-52 overflow-y-auto">
          <div className="flex flex-wrap gap-1.5">
            {contextItems.map((item) => (
              <div
                key={item.id}
                className={cn(
                  'flex items-center gap-1.5 px-2 py-1 rounded-lg text-[11px] group transition-colors',
                  typeColors[item.type]
                )}
              >
                {typeIcons[item.type]}
                <span className="max-w-[110px] truncate">{item.name}</span>
                <span className="text-gray-500 font-mono text-[10px]">{item.tokens}</span>
                <button
                  onClick={() => onRemoveItem(item.id)}
                  className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-black/20 rounded transition-opacity"
                >
                  <X className="w-2.5 h-2.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="relative">
      {/* Trigger Button */}
      <button
        ref={triggerRef}
        onClick={() => {
          if (!isOpen && triggerRef.current) {
            const rect = triggerRef.current.getBoundingClientRect();
            setPosition({ top: rect.bottom + 8, left: rect.left });
          }
          setIsOpen(!isOpen);
        }}
        className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all',
          'bg-gray-800/60 hover:bg-gray-750 border border-gray-700/50',
          isOpen && 'bg-gray-750 border-aqua-500/30'
        )}
      >
        <Brain className={cn('w-3.5 h-3.5', getUsageColor())} />
        <span className="text-gray-300 text-xs">
          <span className={cn('font-medium', getUsageColor())}>{totalTokens.toLocaleString()}</span>
          <span className="text-gray-500"> / {(maxTokens / 1000).toFixed(0)}k</span>
        </span>
        <ChevronDown className={cn(
          'w-3 h-3 text-gray-500 transition-transform duration-200',
          isOpen && 'rotate-180'
        )} />
      </button>

      {/* Dropdown Panel - portaled to body so it escapes overflow-hidden ancestors */}
      {isOpen && dropdownPanel && createPortal(dropdownPanel, document.body)}
    </div>
  );
}
