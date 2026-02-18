import { useState, type ReactNode } from 'react';
import { FileCode, ShieldCheck, Loader2, Check, X, Zap } from 'lucide-react';
import type { ToolCall } from '@/types';
import type { AutoApproveRule } from '@/api';
import { toolIcons } from './ToolCallCard';
import { cn } from '@/utils/cn';

function safeStr(v: unknown): string {
  if (typeof v === 'string') return v;
  if (v == null) return '';
  return typeof v === 'object' ? JSON.stringify(v).slice(0, 50) : JSON.stringify(v);
}

function getActionPreview(
  toolName: string,
  input: Record<string, unknown> | undefined,
): { label: string; preview: ReactNode } {
  const i = input ?? {};
  if (toolName === 'execute_command') {
    const cmd = safeStr(i.command);
    const cwd = i.cwd ? safeStr(i.cwd) : null;
    return {
      label: 'Command to run',
      preview: (
        <>
          <pre className="text-[11px] font-mono text-amber-200/90 bg-gray-900/60 p-2 rounded-md overflow-x-auto whitespace-pre-wrap break-all border border-amber-500/20">
            {cmd || '(empty)'}
          </pre>
          {cwd && (
            <span className="mt-1 block text-[10px] text-gray-500 font-mono">in: {cwd}</span>
          )}
        </>
      ),
    };
  }
  if (toolName === 'read_file') {
    return { label: 'File to read', preview: <span className="font-mono text-amber-200/90">{safeStr(i.path)}</span> };
  }
  if (toolName === 'edit_file') {
    const path = safeStr(i.path);
    const search = safeStr(i.search);
    const replace = safeStr(i.replace);
    const searchPreview = search.length > 80 ? search.slice(0, 80) + '…' : search;
    const replacePreview = replace.length > 80 ? replace.slice(0, 80) + '…' : replace;
    return {
      label: 'Edit to apply',
      preview: (
        <span className="text-[11px]">
          <span className="font-mono text-amber-200/90">{path}</span>
          <span className="text-gray-500"> — replace </span>
          <span className="font-mono text-red-400/90">&quot;{searchPreview}&quot;</span>
          <span className="text-gray-500"> with </span>
          <span className="font-mono text-emerald-400/90">&quot;{replacePreview}&quot;</span>
        </span>
      ),
    };
  }
  if (toolName === 'grep') {
    const pattern = safeStr(i.pattern);
    const path = i.path ? safeStr(i.path) : null;
    return {
      label: 'Search',
      preview: (
        <span className="text-[11px]">
          <span className="font-mono text-amber-200/90">&quot;{pattern}&quot;</span>
          {path && <span className="text-gray-500"> in {path}</span>}
        </span>
      ),
    };
  }
  if (toolName === 'list_files') {
    return { label: 'Directory', preview: <span className="font-mono text-amber-200/90">{safeStr(i.path) || '(project root)'}</span> };
  }
  return {
    label: 'Input',
    preview: (
      <pre className="text-[11px] font-mono text-gray-400 bg-gray-900/60 p-2 rounded-md overflow-x-auto whitespace-pre-wrap break-all">
        {JSON.stringify(i, null, 2)}
      </pre>
    ),
  };
}

function parseCommandParts(
  toolName: string,
  input: Record<string, unknown>,
): { label: string; value: string; key: string }[] {
  const parts: { label: string; value: string; key: string }[] = [];
  parts.push({ label: 'Tool', value: toolName, key: 'tool' });
  if (input.command) {
    parts.push({ label: 'Command', value: safeStr(input.command).slice(0, 60), key: 'command' });
  }
  if (input.cwd) {
    parts.push({ label: 'CWD', value: safeStr(input.cwd), key: 'cwd' });
  }
  if (input.path) {
    const pathStr = safeStr(input.path);
    parts.push({ label: 'Path', value: pathStr, key: 'path' });
    const ext = pathStr.split('.').pop();
    if (ext) {
      parts.push({ label: 'Extension', value: `.${ext}`, key: 'ext' });
    }
    const dir = pathStr.split('/').slice(0, -1).join('/');
    if (dir) {
      parts.push({ label: 'Directory', value: dir, key: 'dir' });
    }
  }
  if (input.pattern) {
    parts.push({ label: 'Pattern', value: safeStr(input.pattern).slice(0, 40), key: 'pattern' });
  }
  if (input.packages && Array.isArray(input.packages)) {
    parts.push({ label: 'Packages', value: (input.packages as string[]).join(', '), key: 'packages' });
  }
  if (input.context) {
    parts.push({ label: 'Context', value: safeStr(input.context).slice(0, 30) + '...', key: 'context' });
  }
  if (input.replacement) {
    parts.push({ label: 'Replacement', value: safeStr(input.replacement).slice(0, 30) + '...', key: 'replacement' });
  }
  return parts.slice(0, 6);
}

function mapPartKeyToField(key: string): AutoApproveRule['field'] {
  if (key === 'tool') return 'tool';
  if (key === 'path') return 'path';
  if (key === 'ext') return 'extension';
  if (key === 'dir') return 'directory';
  if (key === 'command' || key === 'pattern' || key === 'cwd') return 'pattern';
  return 'pattern';
}

interface ApprovalPromptProps {
  readonly pendingApproval: ToolCall;
  readonly autoApproveRules: AutoApproveRule[];
  readonly onApprove: (toolCallId: string) => void;
  readonly onReject: (toolCallId: string) => void;
  readonly onUpdateAutoApproveRules?: (rules: Omit<AutoApproveRule, 'id' | 'createdAt'>[]) => Promise<void> | void;
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

  const commandParts = parseCommandParts(pendingApproval.name, pendingApproval.input ?? {});
  const actionPreview = getActionPreview(pendingApproval.name, pendingApproval.input);

  return (
    <div className="shrink-0 border-t border-gray-700/40 bg-gray-850 p-3">
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
            <span className="text-aqua-400 shrink-0">
              {toolIcons[pendingApproval.name] ?? <FileCode className="w-3.5 h-3.5" />}
            </span>
            <span className="text-xs font-mono text-gray-300">{pendingApproval.name}</span>
          </div>

          <div className="space-y-1">
            <span className="text-[10px] text-gray-500 uppercase tracking-wider font-medium block">
              {actionPreview.label}
            </span>
            <div className="min-w-0">{actionPreview.preview}</div>
          </div>

          {pendingApproval.description && (
            <p className="text-[11px] text-gray-500 leading-relaxed">
              {pendingApproval.description}
            </p>
          )}

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
                        'w-3 h-3 rounded-sm flex items-center justify-center shrink-0 transition-colors',
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
