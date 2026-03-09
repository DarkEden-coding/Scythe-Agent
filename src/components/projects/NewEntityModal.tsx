import { useState } from 'react';
import {
  X,
  ArrowLeft,
  FolderPlus,
  MessageSquarePlus,
  ChevronRight,
  Check,
} from 'lucide-react';
import type { Project } from '@/types';
import { Modal } from '@/components/Modal';
import { api } from '@/api';

interface NewEntityModalProps {
  readonly visible: boolean;
  readonly onClose: () => void;
  readonly projects: Project[];
  readonly onCreateProject?: (name: string, path: string) => Promise<void> | void;
  readonly onCreateChat?: (projectId: string, title?: string) => Promise<void> | void;
}

export function NewEntityModal({
  visible,
  onClose,
  projects,
  onCreateProject,
  onCreateChat,
}: NewEntityModalProps) {
  const [step, setStep] = useState<'choose' | 'project' | 'chat'>('choose');
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectPath, setNewProjectPath] = useState('');
  const [newChatProjectId, setNewChatProjectId] = useState('');
  const [pickError, setPickError] = useState<string | null>(null);
  const [isPickingFolder, setIsPickingFolder] = useState(false);

  const close = () => {
    setStep('choose');
    setNewProjectName('');
    setNewProjectPath('');
    setNewChatProjectId('');
    setPickError(null);
    setIsPickingFolder(false);
    onClose();
  };

  const handleCreateProject = async () => {
    if (!newProjectName.trim() || !newProjectPath) return;
    await onCreateProject?.(newProjectName.trim(), newProjectPath);
    close();
  };

  const handlePickFolder = async () => {
    setIsPickingFolder(true);
    setPickError(null);

    try {
      const res = await api.pickDirectory();
      if (!res.ok) {
        setPickError(res.error ?? 'Failed to open folder picker');
        return;
      }

      if (!res.data.cancelled && res.data.path) {
        setNewProjectPath(res.data.path);
      }
    } catch (error) {
      setPickError(error instanceof Error ? error.message : 'Failed to open folder picker');
    } finally {
      setIsPickingFolder(false);
    }
  };

  const handleCreateChat = async () => {
    if (!newChatProjectId) return;
    await onCreateChat?.(newChatProjectId);
    close();
  };

  return (
    <Modal
      visible={visible}
      onClose={close}
      maxWidth="max-w-sm"
      maxHeight=""
      panelClassName="bg-gray-850 border-gray-700/60 rounded-2xl shadow-black/50 overflow-hidden"
    >
      {step === 'choose' && (
        <>
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700/40">
            <h3 className="text-sm font-semibold text-gray-200">Create New</h3>
            <button
              onClick={close}
              className="p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 rounded-lg transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="p-4 space-y-2.5">
            <button
              onClick={() => setStep('project')}
              className="w-full flex items-center gap-3 px-4 py-3.5 bg-gray-800 hover:bg-gray-750 border border-gray-700/50 hover:border-aqua-500/30 rounded-xl transition-all group"
            >
              <div className="w-9 h-9 rounded-lg bg-aqua-500/10 border border-aqua-500/20 flex items-center justify-center group-hover:bg-aqua-500/20 transition-colors">
                <FolderPlus className="w-4.5 h-4.5 text-aqua-400" />
              </div>
              <div className="text-left">
                <div className="text-sm font-medium text-gray-200">New Project</div>
                <div className="text-[11px] text-gray-500">Create a new project from a folder</div>
              </div>
              <ChevronRight className="w-4 h-4 text-gray-600 ml-auto" />
            </button>
            <button
              onClick={() => setStep('chat')}
              className="w-full flex items-center gap-3 px-4 py-3.5 bg-gray-800 hover:bg-gray-750 border border-gray-700/50 hover:border-aqua-500/30 rounded-xl transition-all group"
            >
              <div className="w-9 h-9 rounded-lg bg-aqua-500/10 border border-aqua-500/20 flex items-center justify-center group-hover:bg-aqua-500/20 transition-colors">
                <MessageSquarePlus className="w-4.5 h-4.5 text-aqua-400" />
              </div>
              <div className="text-left">
                <div className="text-sm font-medium text-gray-200">New Chat</div>
                <div className="text-[11px] text-gray-500">Start a conversation in a project</div>
              </div>
              <ChevronRight className="w-4 h-4 text-gray-600 ml-auto" />
            </button>
          </div>
        </>
      )}

      {step === 'project' && (
        <>
          <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-700/40">
            <button
              onClick={() => setStep('choose')}
              className="p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <h3 className="text-sm font-semibold text-gray-200">New Project</h3>
            <div className="flex-1" />
            <button
              onClick={close}
              className="p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 rounded-lg transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="p-4 space-y-3">
            <div>
              <label htmlFor="new-project-name" className="block text-[11px] font-medium text-gray-400 mb-1.5">Project Name</label>
              <input
                id="new-project-name"
                type="text"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                placeholder="my-awesome-project"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700/50 rounded-xl text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-aqua-500/50 focus:ring-1 focus:ring-aqua-500/20 transition-all"
              />
            </div>
            <div role="group" aria-labelledby="target-folder-label">
              <label id="target-folder-label" className="block text-[11px] font-medium text-gray-400 mb-2">Target Folder</label>
              <button
                type="button"
                onClick={handlePickFolder}
                disabled={isPickingFolder}
                className="w-full py-2.5 text-[11px] font-medium text-aqua-400 bg-aqua-500/10 hover:bg-aqua-500/15 border border-aqua-500/20 rounded-xl transition-colors disabled:opacity-40"
              >
                {isPickingFolder ? 'Opening folder browser...' : 'Browse for folder'}
              </button>
              {pickError && (
                <div className="mt-2 px-3 py-2 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl">
                  {pickError}
                </div>
              )}
              {newProjectPath && (
                <div className="flex items-center gap-2 mt-3 px-3 py-1.5 bg-aqua-500/10 border border-aqua-500/20 rounded-lg">
                  <Check className="w-3 h-3 text-aqua-400 shrink-0" />
                  <span className="text-xs font-mono text-aqua-300 truncate">{newProjectPath}</span>
                  <button onClick={() => setNewProjectPath('')} className="ml-auto p-0.5 text-aqua-400 hover:text-aqua-300">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              )}
              {!newProjectPath && (
                <div className="mt-3 px-3 py-2.5 bg-gray-800 border border-gray-700/50 rounded-xl text-xs text-gray-500">
                  No folder selected yet.
                </div>
              )}
            </div>
            <button
              onClick={handleCreateProject}
              disabled={!newProjectName.trim() || !newProjectPath}
              className="w-full py-2.5 text-sm font-medium text-gray-950 bg-aqua-500 hover:bg-aqua-400 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-colors shadow-lg shadow-aqua-500/20"
            >
              Create Project
            </button>
          </div>
        </>
      )}

      {step === 'chat' && (
        <>
          <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-700/40">
            <button
              onClick={() => setStep('choose')}
              className="p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <h3 className="text-sm font-semibold text-gray-200">New Chat</h3>
            <div className="flex-1" />
            <button
              onClick={close}
              className="p-1 text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 rounded-lg transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="p-4 space-y-3">
            <div>
              <label htmlFor="new-chat-project" className="block text-[11px] font-medium text-gray-400 mb-1.5">Project</label>
              <select
                id="new-chat-project"
                value={newChatProjectId}
                onChange={(e) => setNewChatProjectId(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700/50 rounded-xl text-sm text-gray-200 focus:outline-none focus:border-aqua-500/50 focus:ring-1 focus:ring-aqua-500/20 transition-all appearance-none"
              >
                <option value="" className="bg-gray-800 text-gray-400">
                  Select a project...
                </option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id} className="bg-gray-800">
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={handleCreateChat}
              disabled={!newChatProjectId}
              className="w-full py-2.5 text-sm font-medium text-gray-950 bg-aqua-500 hover:bg-aqua-400 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-colors shadow-lg shadow-aqua-500/20"
            >
              Create Chat
            </button>
          </div>
        </>
      )}
    </Modal>
  );
}
