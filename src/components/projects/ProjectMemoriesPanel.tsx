import { useEffect, useMemo, useState } from 'react';
import { Brain, Pencil, Plus, RefreshCw, Trash2 } from 'lucide-react';
import type { ProjectMemory } from '@/types';
import { Modal } from '@/components/Modal';
import { ProjectMemoryEditor } from './ProjectMemoryEditor';

interface ProjectMemoriesPanelProps {
  readonly projectId: string;
  readonly projectName: string;
  readonly memories: ProjectMemory[];
  readonly visible: boolean;
  readonly onClose: () => void;
  readonly onLoad: (projectId: string, options?: { force?: boolean }) => Promise<unknown> | void;
  readonly onSave: (projectId: string, payload: { title: string; contentMarkdown: string }) => Promise<{ ok?: boolean; error?: string } | void> | void;
  readonly onDelete: (projectId: string, title: string) => Promise<{ ok?: boolean; error?: string } | void> | void;
}

export function ProjectMemoriesPanel({
  projectId,
  projectName,
  memories,
  visible,
  onClose,
  onLoad,
  onSave,
  onDelete,
}: ProjectMemoriesPanelProps) {
  const [editingTitle, setEditingTitle] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);

  useEffect(() => {
    if (!visible || hasLoaded) return;
    Promise.resolve(onLoad(projectId, { force: true })).finally(() => setHasLoaded(true));
  }, [visible, hasLoaded, onLoad, projectId]);

  useEffect(() => {
    if (!visible) {
      setShowCreate(false);
      setEditingTitle(null);
      setError(null);
      setBusy(false);
    }
  }, [visible]);

  const editingMemory = useMemo(
    () => memories.find((memory) => memory.title === editingTitle) ?? null,
    [editingTitle, memories],
  );

  const closeEditor = () => {
    setShowCreate(false);
    setEditingTitle(null);
    setError(null);
  };

  const handleSave = async (payload: { title: string; contentMarkdown: string }) => {
    setBusy(true);
    setError(null);
    try {
      const res = await onSave(projectId, payload);
      if (res && typeof res === 'object' && 'ok' in res && !res.ok) {
        setError(typeof res.error === 'string' ? res.error : 'Failed to save memory');
        return;
      }
      closeEditor();
      setHasLoaded(true);
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (title: string) => {
    if (!globalThis.confirm(`Delete project memory "${title}"?`)) return;
    setBusy(true);
    setError(null);
    try {
      const res = await onDelete(projectId, title);
      if (res && typeof res === 'object' && 'ok' in res && !res.ok) {
        setError(typeof res.error === 'string' ? res.error : 'Failed to delete memory');
      } else if (editingTitle === title) {
        closeEditor();
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      visible={visible}
      onClose={onClose}
      title="Project Memories"
      subtitle={projectName}
      icon={<Brain className="h-5 w-5 text-aqua-400" />}
      maxWidth="max-w-2xl"
      panelClassName="min-h-[420px]"
    >
      <div className="space-y-3 px-4 py-4">
        <div className="flex items-center justify-between gap-3 rounded-xl border border-gray-700/40 bg-gray-850/70 px-3 py-2.5">
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-aqua-500/20 bg-aqua-500/10">
              <Brain className="h-3.5 w-3.5 text-aqua-400" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium text-gray-200">Project Memories</div>
              <div className="text-[10px] text-gray-500">
                Durable user preferences and corrections only
              </div>
            </div>
            <span className="rounded-md bg-gray-800/90 px-1.5 py-0.5 text-[10px] text-gray-400">
              {memories.length}
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => {
                setHasLoaded(false);
                void Promise.resolve(onLoad(projectId, { force: true })).finally(() => setHasLoaded(true));
              }}
              className="rounded-md p-1 text-gray-500 hover:bg-gray-800 hover:text-gray-300"
              title="Refresh project memories"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => {
                setEditingTitle(null);
                setShowCreate(true);
                setError(null);
              }}
              className="inline-flex items-center gap-1 rounded-lg bg-aqua-500/10 px-2 py-1 text-[11px] text-aqua-400 hover:bg-aqua-500/20"
            >
              <Plus className="h-3.5 w-3.5" />
              Add
            </button>
          </div>
        </div>

          <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-[11px] leading-relaxed text-amber-100/80">
            These memories are injected by title into conversations. Keep them short, stable, and limited to user preferences/corrections — not code, plans, or retrieved context.
          </div>

          {showCreate && (
            <ProjectMemoryEditor
              initialTitle=""
              initialContentMarkdown=""
              busy={busy}
              error={error}
              onCancel={closeEditor}
              onSave={handleSave}
            />
          )}

          {!showCreate && !editingMemory && memories.length === 0 && (
            <div className="rounded-xl border border-dashed border-gray-700/60 bg-gray-800/30 px-4 py-4 text-center">
              <div className="text-sm text-gray-300">No project memories yet</div>
              <div className="mt-1 text-[11px] text-gray-500">
                Add stable guidance like formatting preferences or recurring corrections.
              </div>
            </div>
          )}

          <div className="space-y-2">
            {memories.map((memory) => (
              editingTitle === memory.title ? (
                <ProjectMemoryEditor
                  key={memory.id}
                  initialTitle={memory.title}
                  initialContentMarkdown={memory.contentMarkdown}
                  busy={busy}
                  error={error}
                  onCancel={closeEditor}
                  onSave={handleSave}
                />
              ) : (
                <div key={memory.id} className="rounded-xl border border-gray-700/50 bg-gray-800/40 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-gray-200">{memory.title}</div>
                      <div className="mt-1 whitespace-pre-wrap text-xs leading-relaxed text-gray-400">
                        {memory.contentMarkdown}
                      </div>
                      <div className="mt-2 text-[10px] text-gray-500">
                        Updated {memory.updatedAt.toLocaleString()}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => {
                          setShowCreate(false);
                          setEditingTitle(memory.title);
                          setError(null);
                        }}
                        className="rounded-md p-1 text-gray-500 hover:bg-gray-700/50 hover:text-gray-300"
                        title="Edit memory"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleDelete(memory.title)}
                        className="rounded-md p-1 text-gray-500 hover:bg-red-500/10 hover:text-red-300"
                        title="Delete memory"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              )
            ))}
          </div>
      </div>
    </Modal>
  );
}
