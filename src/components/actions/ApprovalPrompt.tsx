import { useState } from 'react';
import { FileCode, ShieldCheck, Loader2, Check, X, Zap } from 'lucide-react';
import type { ToolCall } from '@/types';
import type { AutoApproveRule } from '@/api';
import { toolIcons } from './ToolCallCard';
import { cn } from '@/utils/cn';

function parseCommandParts(
  toolName: string,
  input: Record<string, unknown>,
): { label: string; value: string; key: string }[] {
  const parts: { label: string; value: string; key: string }[] = [];
  parts.push({ label: 'Tool', value: toolName, key: 'tool' });
  if (input.path) {
    parts.push({ label: 'Path', value: String(input.path), key: 'path' });
    const ext = String(input.path).split('.').pop();
    if (ext) {
      parts.push({ label: 'Extension', value: `.${ext}`, key: 'ext' });
    }
    const dir = String(input.path).split('/').slice(0, -1).join('/');
    if (dir) {
      parts.push({ label: 'Directory', value: dir, key: 'dir' });
    }
  }
  if (input.packages && Array.isArray(input.packages)) {
    parts.push({ label: 'Packages', value: (input.packages as string[]).join(', '), key: 'packages' });
  }
  if (input.context) {
    parts.push({ label: 'Context', value: String(input.context).slice(0, 30) + '...', key: 'context' });
  }
  if (input.replacement) {
    parts.push({ label: 'Replacement', value: String(input.replacement).slice(0, 30) + '...', key: 'replacement' });
  }
  return parts.slice(0, 5);
}

function mapPartKeyToField(key: string): AutoApproveRule['field'] {
  if (key === 'tool') return 'tool';
  if (key === 'path') return 'path';
  if (key === 'ext') return 'extension';
  if (key === 'dir') return 'directory';
  return 'pattern';
}

interface ApprovalPromptProps {
  pendingApproval: ToolCall;
  autoApproveRules: AutoApproveRule[];
  onApprove: (toolCallId: string) => void;
  onReject: (toolCallId: string) => void;
  onUpdateAutoApproveRules?: (rules: Omit<AutoApproveRule, 'id' | 'createdAt'>[]) => Promise<void> | void;
}

export function ApprovalPrompt({
  pendingApproval,
  autoApproveRules,
  onApprove,
  onReject,
  onUpdateAutoApproveRules,
}: ApprovalPromptProps) {
  const [autoApproveRuleKeys, setAutoApproveRuleKeys] = useState<Set<string>>(
    new Set(autoApproveRules.map((rule) => `${rule.field}:${rule.value}`)),
  );

  const toggleAutoApprove = (key: string, value: string) => {
    const dbField = mapPartKeyToField(key);
    const token = `${dbField}:${value}`;
    const next = new Set(autoApproveRuleKeys);
    if (next.has(token)) {
      next.delete(token);
    } else {
      next.add(token);
    }
    setAutoApproveRuleKeys(next);
    onUpdateAutoApproveRules?.(
      Array.from(next).map((entry) => {
        const [field, ...rest] = entry.split(':');
        return {
          field: field as AutoApproveRule['field'],
          value: rest.join(':'),
          enabled: true,
        };
      }),
    );
  };

  const commandParts = parseCommandParts(pendingApproval.name, pendingApproval.input);

  return (
    <div className="flex-shrink-0 border-t border-gray-700/40 bg-gray-850 p-3">
      <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 overflow-hidden shadow-lg">
        <div className="flex items-center gap-2 px-3 py-2 bg-amber-500/10 border-b border-amber-500/20">
          <div className="w-5 h-5 rounded-md bg-amber-500/20 flex items-center justify-center">
            <ShieldCheck className="w-3 h-3 text-amber-400" />
          </div>
          <span className="text-xs font-medium text-amber-300">Tool Approval Required</span>
          <Loader2 className="w-3 h-3 text-amber-400/60 animate-spin ml-auto" />
        </div>

        <div className="p-3 space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-aqua-400">
              {toolIcons[pendingApproval.name] ?? <FileCode className="w-3.5 h-3.5" />}
            </span>
            <span className="text-xs font-mono text-gray-300">{pendingApproval.name}</span>
            <span className="text-[10px] text-gray-600 font-mono">
              {String(pendingApproval.input.path ?? '')}
            </span>
          </div>

          <p className="text-[11px] text-gray-500 leading-relaxed">
            {pendingApproval.description ?? 'Waiting for approval to run this tool call.'}
          </p>

          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <Zap className="w-3 h-3 text-emerald-400/60" />
              <span className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">
                Auto-approve in future
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {commandParts.map((part) => {
                const normalized = `${mapPartKeyToField(part.key)}:${part.value}`;
                const isAutoApproved = autoApproveRuleKeys.has(normalized);
                return (
                  <button
                    key={part.key}
                    onClick={() => toggleAutoApprove(part.key, part.value)}
                    className={cn(
                      'inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-mono transition-all border',
                      isAutoApproved
                        ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
                        : 'bg-gray-800/50 border-gray-700/40 text-gray-400 hover:border-gray-600/50 hover:text-gray-300',
                    )}
                    title={`${part.label}: ${part.value}`}
                  >
                    <span
                      className={cn(
                        'w-3 h-3 rounded-sm flex items-center justify-center flex-shrink-0 transition-colors',
                        isAutoApproved ? 'bg-emerald-500/30' : 'bg-gray-700/50',
                      )}
                    >
                      {isAutoApproved && <Check className="w-2 h-2 text-emerald-300" />}
                    </span>
                    <span className="text-gray-500">{part.label}:</span>
                    <span
                      className={cn(
                        'max-w-[100px] truncate',
                        isAutoApproved ? 'text-emerald-300' : 'text-gray-300',
                      )}
                    >
                      {part.value}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={() => onApprove(pendingApproval.id)}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/30 text-emerald-300 text-xs font-medium transition-colors"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Approve</span>
            </button>
            <button
              onClick={() => onReject(pendingApproval.id)}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 text-xs font-medium transition-colors"
            >
              <X className="w-3.5 h-3.5" />
              <span>Reject</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
