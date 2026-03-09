import { useEffect, useState } from 'react';
import { Save, X } from 'lucide-react';

interface ProjectMemoryEditorProps {
  readonly initialTitle?: string;
  readonly initialContentMarkdown?: string;
  readonly busy?: boolean;
  readonly error?: string | null;
  readonly onCancel: () => void;
  readonly onSave: (payload: { title: string; contentMarkdown: string }) => Promise<void> | void;
}

export function ProjectMemoryEditor({
  initialTitle = '',
  initialContentMarkdown = '',
  busy = false,
  error = null,
  onCancel,
  onSave,
}: ProjectMemoryEditorProps) {
  const [title, setTitle] = useState(initialTitle);
  const [contentMarkdown, setContentMarkdown] = useState(initialContentMarkdown);

  useEffect(() => {
    setTitle(initialTitle);
  }, [initialTitle]);

  useEffect(() => {
    setContentMarkdown(initialContentMarkdown);
  }, [initialContentMarkdown]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !contentMarkdown.trim() || busy) return;
    await onSave({ title: title.trim(), contentMarkdown: contentMarkdown.trim() });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3 rounded-xl border border-gray-700/50 bg-gray-800/60 p-3">
      <div>
        <label htmlFor="project-memory-title" className="mb-1.5 block text-[11px] font-medium text-gray-400">
          Memory title
        </label>
        <input
          id="project-memory-title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={120}
          placeholder="e.g. Prefer concise answers"
          className="w-full rounded-xl border border-gray-700/50 bg-gray-800 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-aqua-500/50 focus:outline-none focus:ring-1 focus:ring-aqua-500/20"
        />
      </div>

      <div>
        <label htmlFor="project-memory-content" className="mb-1.5 block text-[11px] font-medium text-gray-400">
          Durable user preference or correction
        </label>
        <textarea
          id="project-memory-content"
          value={contentMarkdown}
          onChange={(e) => setContentMarkdown(e.target.value)}
          rows={5}
          placeholder="Store only stable user preferences/corrections. Avoid project data, plans, dumps, or code."
          className="w-full resize-y rounded-xl border border-gray-700/50 bg-gray-800 px-3 py-2 text-sm leading-relaxed text-gray-200 placeholder-gray-600 focus:border-aqua-500/50 focus:outline-none focus:ring-1 focus:ring-aqua-500/20"
        />
        <div className="mt-1 flex items-center justify-between text-[10px] text-gray-500">
          <span>Minimal, project-scoped, preference-only memory.</span>
          <span>{contentMarkdown.length}/2000</span>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">
          {error}
        </div>
      )}

      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-600 px-3 py-2 text-xs text-gray-200 hover:bg-gray-700/40 disabled:opacity-50"
        >
          <X className="h-3.5 w-3.5" />
          Cancel
        </button>
        <button
          type="submit"
          disabled={busy || !title.trim() || !contentMarkdown.trim()}
          className="inline-flex items-center gap-1 rounded-lg bg-aqua-500 px-3 py-2 text-xs font-medium text-gray-950 hover:bg-aqua-400 disabled:opacity-50"
        >
          <Save className="h-3.5 w-3.5" />
          {busy ? 'Saving…' : 'Save memory'}
        </button>
      </div>
    </form>
  );
}
