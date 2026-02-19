import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { MessageSquare, Terminal, FileText, ChevronDown, Bug } from 'lucide-react';
import { ContextItem } from '../types';
import { cn } from '../utils/cn';
import { api } from '../api';

interface ContextDropdownProps {
  readonly contextItems: ContextItem[];
  readonly maxTokens: number;
  readonly chatId?: string | null;
}

const typeIcons: Record<string, React.ReactNode> = {
  conversation: <MessageSquare className="w-3 h-3" />,
  tool_output: <Terminal className="w-3 h-3" />,
  summary: <FileText className="w-3 h-3" />,
};

const typeColors: Record<string, string> = {
  conversation: 'text-aqua-300 bg-aqua-500/10 border border-aqua-500/20',
  tool_output: 'text-teal-300 bg-teal-500/10 border border-teal-500/20',
  summary: 'text-amber-300 bg-amber-500/10 border border-amber-500/20',
};

const PIE_COLORS: Record<string, string> = {
  conversation: '#22c55e',
  tool_output: '#a855f7',
  summary: '#f97316',
};

const REMAINING_COLOR = '#3f3f46';

function PieChart({
  segments,
  maxTokens,
}: Readonly<{
  segments: { type: string; tokens: number }[];
  maxTokens: number;
}>) {
  const usedTokens = segments.reduce((s, seg) => s + seg.tokens, 0);
  const remainingTokens = Math.max(0, maxTokens - usedTokens);
  const total = maxTokens;
  const cx = 32;
  const cy = 32;
  const r = 28;
  const tau = 2 * Math.PI;
  let acc = -Math.PI / 2;

  const allSegments = [
    ...segments.filter((s) => s.tokens > 0),
    ...(remainingTokens > 0 ? [{ type: '_remaining', tokens: remainingTokens }] : []),
  ];

  const paths = allSegments.map((seg) => {
    const pct = seg.tokens / total;
    const start = acc;
    acc += pct * tau;
    const x1 = cx + r * Math.cos(start);
    const y1 = cy + r * Math.sin(start);
    const x2 = cx + r * Math.cos(acc);
    const y2 = cy + r * Math.sin(acc);
    const large = pct > 0.5 ? 1 : 0;
    const d = `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`;
    const fill = seg.type === '_remaining' ? REMAINING_COLOR : PIE_COLORS[seg.type] ?? PIE_COLORS.tool_output;
    const opacity = seg.type === '_remaining' ? 0.5 : 0.9;
    return (
      <path key={seg.type} d={d} fill={fill} opacity={opacity} />
    );
  });

  return (
    <svg width={64} height={64} viewBox="0 0 64 64" className="shrink-0">
      {paths}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#52525b" strokeWidth={1.5} />
    </svg>
  );
}

function UsageRing({ percentage, stroke }: { percentage: number; stroke: string }) {
  const r = 8;
  const strokeWidth = 2.5;
  const norm = r - strokeWidth / 2;
  const circ = norm * 2 * Math.PI;
  const dash = circ - (Math.min(percentage, 100) / 100) * circ;
  return (
    <svg width={20} height={20} className="-rotate-90 shrink-0">
      <circle
        cx={10}
        cy={10}
        r={norm}
        fill="none"
        stroke="#2a2a3a"
        strokeWidth={strokeWidth}
      />
      <circle
        cx={10}
        cy={10}
        r={norm}
        fill="none"
        stroke={stroke}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={dash}
        className="transition-all duration-300"
      />
    </svg>
  );
}

function escapeHtml(s: string): string {
  return s
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

const typeLabels: Record<string, string> = {
  conversation: 'Conversation',
  tool_output: 'Tool Outputs',
  summary: 'Summaries',
};

export function ContextDropdown({
  contextItems,
  maxTokens,
  chatId,
}: ContextDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const totalTokens = contextItems.reduce((sum, item) => sum + item.tokens, 0);
  const usagePercentage = Math.min((totalTokens / maxTokens) * 100, 100);

  const getUsageStroke = () => {
    if (usagePercentage > 90) return '#ef4444';
    if (usagePercentage > 70) return '#f59e0b';
    return '#22d3d8';
  };

  const groupedByType = contextItems.reduce<Record<string, { count: number; tokens: number }>>((acc, item) => {
    const type = item.type === 'file' ? 'tool_output' : item.type;
    if (!acc[type]) acc[type] = { count: 0, tokens: 0 };
    acc[type].count++;
    acc[type].tokens += item.tokens;
    return acc;
  }, {});

  const pieSegments = Object.entries(groupedByType)
    .map(([type, data]) => ({ type, tokens: data.tokens }))
    .filter((s) => s.tokens > 0)
    .sort((a, b) => b.tokens - a.tokens);

  const top5Items = [...contextItems].sort((a, b) => b.tokens - a.tokens).slice(0, 5);

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

  const dropdownPanel = isOpen && (
    <div
      ref={dropdownRef}
      className="fixed z-50 min-w-[380px] animate-dropdown"
      style={{ top: position.top, left: position.left }}
    >
      <div className="bg-gray-850 border border-gray-700/60 rounded-2xl shadow-2xl shadow-black/40 overflow-hidden">
        <div className="p-4 border-b border-gray-700/40">
          <div className="flex items-start gap-4">
            <PieChart segments={pieSegments} maxTokens={maxTokens} />
            <div className="flex-1 min-w-0">
              <span className="text-xs font-medium text-gray-300">Context by category</span>
              <div className="mt-2 space-y-1">
                {pieSegments.map((seg) => (
                  <div key={seg.type} className="flex items-center justify-between text-[10px]">
                    <div className="flex items-center gap-1.5">
                      <span
                        className="w-1.5 h-1.5 rounded-full shrink-0"
                        style={{ backgroundColor: PIE_COLORS[seg.type] ?? PIE_COLORS.tool_output }}
                      />
                      <span className="text-gray-400">{typeLabels[seg.type] ?? 'Tool Outputs'}</span>
                    </div>
                    <span className="text-gray-500 font-mono">{seg.tokens.toLocaleString()}</span>
                  </div>
                ))}
                {Math.max(0, maxTokens - totalTokens) > 0 && (
                  <div className="flex items-center justify-between text-[10px]">
                    <div className="flex items-center gap-1.5">
                      <span
                        className="w-1.5 h-1.5 rounded-full shrink-0"
                        style={{ backgroundColor: REMAINING_COLOR }}
                      />
                      <span className="text-gray-400">Remaining</span>
                    </div>
                    <span className="text-gray-500 font-mono">{(maxTokens - totalTokens).toLocaleString()}</span>
                  </div>
                )}
                {pieSegments.length === 0 && totalTokens === 0 && (
                  <span className="text-[10px] text-gray-500">No context yet</span>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="p-3">
          <span className="text-[10px] font-medium text-gray-400 block mb-2">Top 5 by tokens</span>
          <div className="space-y-1">
            {top5Items.map((item) => (
              <div
                key={item.id}
                title={item.full_name ?? item.name}
                className={cn(
                  'flex items-center gap-2 px-2 py-1.5 rounded-lg text-[11px]',
                  typeColors[item.type] ?? typeColors.tool_output
                )}
              >
                {typeIcons[item.type] ?? typeIcons.tool_output}
                <span className="flex-1 min-w-0 truncate">{item.name}</span>
                <span className="text-gray-500 font-mono text-[10px] shrink-0">{item.tokens.toLocaleString()}</span>
              </div>
            ))}
            {top5Items.length === 0 && (
              <span className="text-[10px] text-gray-500">—</span>
            )}
          </div>

          {chatId && (
            <div className="mt-3 pt-3 border-t border-gray-700/40">
              <button
                type="button"
                onClick={async () => {
                  const res = await api.getChatDebug(chatId);
                  if (!res.ok || !res.data) return;
                  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Chat Debug - ${chatId}</title><style>body{background:#1a1a24;color:#e5e7eb;font-family:ui-monospace,monospace;padding:1.5rem;margin:0;font-size:13px;line-height:1.5}pre{white-space:pre-wrap;word-wrap:break-word;margin:0}</style></head><body><pre>${escapeHtml(JSON.stringify(res.data, null, 2))}</pre></body></html>`;
                  const blob = new Blob([html], { type: 'text/html' });
                  window.open(URL.createObjectURL(blob), '_blank', 'noopener');
                }}
                className="flex items-center gap-1.5 w-full px-2 py-1.5 rounded-lg text-[11px] text-gray-400 hover:bg-gray-700/50 hover:text-aqua-400 transition-colors"
                title="Open debug JSON in new tab"
              >
                <Bug className="w-3 h-3" />
                View API debug
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div className="relative">
      {/* Trigger Button */}
      <button
        ref={triggerRef}
        title={`${totalTokens.toLocaleString()} / ${(maxTokens / 1000).toFixed(0)}k tokens`}
        onClick={() => {
          if (!isOpen && triggerRef.current) {
            const rect = triggerRef.current.getBoundingClientRect();
            setPosition({ top: rect.bottom + 8, left: rect.left });
          }
          setIsOpen(!isOpen);
        }}
        className={cn(
          'flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-sm transition-all',
          'bg-gray-800/60 hover:bg-gray-750 border border-gray-700/50',
          isOpen && 'bg-gray-750 border-aqua-500/30'
        )}
      >
        <UsageRing percentage={usagePercentage} stroke={getUsageStroke()} />
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
