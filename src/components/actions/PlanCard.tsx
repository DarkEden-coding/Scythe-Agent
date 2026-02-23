import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, FilePenLine, RefreshCw, Save } from 'lucide-react';
import { Markdown } from '@/components/Markdown';
import type { ProjectPlan } from '@/types';

interface SavePlanResult {
  ok: boolean;
  error?: string;
  data?: {
    conflict: boolean;
    plan: ProjectPlan;
  };
}

interface ApprovePlanResult {
  ok: boolean;
  error?: string;
  data?: {
    plan: ProjectPlan;
    implementationChatId?: string;
  };
}

interface PlanCardProps {
  readonly plan: ProjectPlan;
  readonly onSave: (planId: string, content: string, baseRevision: number) => Promise<SavePlanResult>;
  readonly onApprove: (
    planId: string,
    action: 'keep_context' | 'clear_context',
  ) => Promise<ApprovePlanResult>;
  readonly onImplementationChat?: (chatId: string) => void;
}

export function PlanCard({
  plan,
  onSave,
  onApprove,
  onImplementationChat,
}: PlanCardProps) {
  const [draft, setDraft] = useState(plan.content ?? '');
  const [baseRevision, setBaseRevision] = useState(plan.revision);
  const [editing, setEditing] = useState(false);
  const [staleConflict, setStaleConflict] = useState(false);
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canonicalContent = plan.content ?? '';
  const dirty = draft !== canonicalContent;

  useEffect(() => {
    if (!dirty) {
      setDraft(canonicalContent);
      setBaseRevision(plan.revision);
      setStaleConflict(false);
      return;
    }
    if (plan.revision !== baseRevision) {
      setStaleConflict(true);
    }
  }, [plan.id, plan.revision, canonicalContent, baseRevision, dirty]);

  const updatedLabel = useMemo(() => {
    const time = Number.isFinite(plan.updatedAt.getTime())
      ? plan.updatedAt.toLocaleString()
      : 'Unknown';
    return `${plan.status} · rev ${plan.revision} · ${time}`;
  }, [plan.status, plan.revision, plan.updatedAt]);

  const handleSave = async () => {
    if (!dirty || staleConflict) return;
    setSaving(true);
    setError(null);
    try {
      const res = await onSave(plan.id, draft, baseRevision);
      if (!res.ok) {
        setError(res.error ?? 'Failed to save plan');
        return;
      }
      if (res.data?.conflict) {
        setStaleConflict(true);
        setError('Plan changed externally. Refresh before saving.');
        return;
      }
      if (res.data?.plan) {
        setBaseRevision(res.data.plan.revision);
        setStaleConflict(false);
      }
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const handleApprove = async (action: 'keep_context' | 'clear_context') => {
    if (staleConflict) return;
    setApproving(true);
    setError(null);
    try {
      const res = await onApprove(plan.id, action);
      if (!res.ok) {
        setError(res.error ?? 'Failed to approve plan');
        return;
      }
      if (action === 'clear_context' && res.data?.implementationChatId) {
        onImplementationChat?.(res.data.implementationChatId);
      }
    } finally {
      setApproving(false);
    }
  };

  return (
    <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-3 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-xs text-cyan-300 font-medium">{plan.title}</div>
          <div className="text-[10px] text-gray-400">{updatedLabel}</div>
        </div>
        <button
          type="button"
          onClick={() => setEditing((prev) => !prev)}
          className="inline-flex items-center gap-1 px-2 py-1 text-[10px] rounded-md border border-gray-600/40 text-gray-200 hover:bg-gray-800/70"
        >
          <FilePenLine className="w-3 h-3" />
          {editing ? 'Preview' : 'Edit'}
        </button>
      </div>

      {staleConflict && (
        <div className="rounded-md border border-amber-400/40 bg-amber-500/10 px-2 py-1.5 text-[11px] text-amber-100 flex items-center justify-between gap-2">
          <span>Plan changed externally. Refresh to reconcile.</span>
          <button
            type="button"
            className="inline-flex items-center gap-1 px-2 py-1 rounded border border-amber-400/40 bg-amber-500/10 hover:bg-amber-500/20"
            onClick={() => {
              setDraft(canonicalContent);
              setBaseRevision(plan.revision);
              setStaleConflict(false);
              setError(null);
            }}
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
        </div>
      )}

      {editing ? (
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={16}
          className="w-full rounded-lg border border-gray-700/50 bg-gray-900/70 p-2 text-xs text-gray-100 font-mono focus:outline-none focus:ring-1 focus:ring-cyan-500/40"
        />
      ) : (
        <div className="rounded-lg border border-gray-700/40 bg-gray-900/60 p-2 max-h-[420px] overflow-auto text-xs text-gray-200">
          <Markdown content={canonicalContent || '_No plan markdown content yet._'} />
        </div>
      )}

      {error && <div className="text-[11px] text-red-300">{error}</div>}

      <div className="flex flex-wrap items-center gap-2">
        {editing && (
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !dirty || staleConflict}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 text-[11px] rounded-md bg-cyan-500 text-gray-950 font-medium hover:bg-cyan-400 disabled:opacity-50"
          >
            <Save className="w-3 h-3" />
            Save Markdown
          </button>
        )}
        <button
          type="button"
          onClick={() => handleApprove('clear_context')}
          disabled={approving || staleConflict || dirty}
          className="inline-flex items-center gap-1 px-2.5 py-1.5 text-[11px] rounded-md bg-cyan-500 text-gray-950 font-medium hover:bg-cyan-400 disabled:opacity-50"
        >
          <CheckCircle2 className="w-3 h-3" />
          Clear Context + Implement
        </button>
        <button
          type="button"
          onClick={() => handleApprove('keep_context')}
          disabled={approving || staleConflict || dirty}
          className="inline-flex items-center gap-1 px-2.5 py-1.5 text-[11px] rounded-md border border-gray-500/60 text-gray-200 hover:bg-gray-800/70 disabled:opacity-50"
        >
          <CheckCircle2 className="w-3 h-3" />
          Keep Context + Implement
        </button>
      </div>
    </div>
  );
}
