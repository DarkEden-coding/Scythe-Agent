import { Plus, Pencil, Trash2, RotateCcw, ChevronDown, ChevronRight } from 'lucide-react';
import type { FileEdit } from '@/types';
import { DiffPreview } from './DiffPreview';
import { cn } from '@/utils/cn';

interface FileEditCardProps {
  readonly edit: FileEdit;
  readonly isExpanded: boolean;
  readonly onToggle: () => void;
  readonly onRevert: () => void;
}

function getActionLabel(action: FileEdit['action']): string {
  if (action === 'create') return 'Created';
  if (action === 'edit') return 'Modified';
  return 'Deleted';
}

function getActionColor(action: FileEdit['action']): string {
  if (action === 'create') return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
  if (action === 'edit') return 'text-aqua-400 bg-aqua-500/10 border-aqua-500/20';
  return 'text-red-400 bg-red-500/10 border-red-500/20';
}

export function FileEditCard({ edit, isExpanded, onToggle, onRevert }: FileEditCardProps) {
  const actionLabel = getActionLabel(edit.action);
  const actionColor = getActionColor(edit.action);

  return (
    <div className="rounded-xl overflow-hidden bg-gray-800/50 border border-gray-700/30 shadow-sm w-full">
      <div className="flex items-center gap-2 px-3 py-2 hover:bg-gray-750/30 transition-colors">
        <button onClick={onToggle} className="text-gray-600 hover:text-gray-400 shrink-0">
          {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        </button>
        <span
          className={cn(
            'w-5 h-5 flex items-center justify-center rounded-md text-xs shrink-0',
            edit.action === 'create' && 'bg-emerald-500/15 text-emerald-400',
            edit.action === 'edit' && 'bg-aqua-500/15 text-aqua-400',
            edit.action === 'delete' && 'bg-red-500/15 text-red-400',
          )}
        >
          {edit.action === 'create' && <Plus className="w-3 h-3" />}
          {edit.action === 'edit' && <Pencil className="w-3 h-3" />}
          {edit.action === 'delete' && <Trash2 className="w-3 h-3" />}
        </span>
        <span className="flex-1 text-xs text-gray-300 font-mono truncate min-w-0">
          {edit.filePath}
        </span>
        <span
          className={cn(
            'text-[10px] px-1.5 py-0.5 rounded border font-medium whitespace-nowrap shrink-0',
            actionColor,
          )}
        >
          {actionLabel}
        </span>
        <button
          onClick={onRevert}
          className="p-1 text-gray-600 hover:text-amber-400 hover:bg-gray-700/50 rounded-md transition-colors shrink-0"
          title="Revert this file edit"
        >
          <RotateCcw className="w-3 h-3" />
        </button>
      </div>

      {isExpanded && edit.diff && (
        <div className="px-3 pb-3">
          <DiffPreview diff={edit.diff} action={edit.action} />
        </div>
      )}
    </div>
  );
}
