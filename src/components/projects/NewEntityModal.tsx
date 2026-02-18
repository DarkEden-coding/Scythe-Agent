import { useState } from 'react';
import {
  X,
  ArrowLeft,
  FolderPlus,
  MessageSquarePlus,
  ChevronRight,
  Folder,
  Check,
} from 'lucide-react';
import type { Project } from '@/types';
import { Modal } from '@/components/Modal';
import { useFilesystemBrowser } from '@/api';

interface NewEntityModalProps {
  visible: boolean;
  onClose: () => void;
  projects: Project[];
  onCreateProject?: (name: string, path: string) => Promise<void> | void;
  onCreateChat?: (projectId: string, title?: string) => Promise<void> | void;
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
  const fs = useFilesystemBrowser();

  const close = () => {
    setStep('choose');
    setNewProjectName('');
    setNewProjectPath('');
    setNewChatProjectId('');
    onClose();
  };

  const currentFolders = (fs.data?.children ?? []).filter((item) => item.kind === 'directory');

  const handleCreateProject = async () => {
    if (!newProjectName.trim() || !newProjectPath) return;
    await onCreateProject?.(newProjectName.trim(), newProjectPath);
    close();
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
              onClick={async () => {
                setStep('project');
                await fs.load();
              }}
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
              <label className="block text-[11px] font-medium text-gray-400 mb-1.5">Project Name</label>
              <input
                type="text"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                placeholder="my-awesome-project"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700/50 rounded-xl text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-aqua-500/50 focus:ring-1 focus:ring-aqua-500/20 transition-all"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-gray-400 mb-1.5">Target Folder</label>
              {newProjectPath && (
                <div className="flex items-center gap-2 mb-2 px-3 py-1.5 bg-aqua-500/10 border border-aqua-500/20 rounded-lg">
                  <Check className="w-3 h-3 text-aqua-400 flex-shrink-0" />
                  <span className="text-xs font-mono text-aqua-300 truncate">{newProjectPath}</span>
                  <button onClick={() => setNewProjectPath('')} className="ml-auto p-0.5 text-aqua-400 hover:text-aqua-300">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              )}
              <div className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 border border-gray-700/50 rounded-t-xl text-[11px] font-mono text-gray-400">
                <span className="truncate">{fs.path || 'Loading...'}</span>
              </div>
              <div className="bg-gray-800 border border-t-0 border-gray-700/50 rounded-b-xl max-h-40 overflow-y-auto">
                {fs.loading && <div className="px-3 py-2 text-xs text-gray-500">Loading directories...</div>}
                {fs.error && <div className="px-3 py-2 text-xs text-red-400">{fs.error}</div>}
                {fs.data?.parentPath && (
                  <button
                    onClick={() => fs.load(fs.data?.parentPath ?? undefined)}
                    className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-400 hover:bg-gray-750 hover:text-gray-200 transition-colors"
                  >
                    <ArrowLeft className="w-3 h-3" />
                    <span>..</span>
                  </button>
                )}
                {currentFolders.map((folder) => (
                  <button
                    key={folder.path}
                    onClick={() => fs.load(folder.path)}
                    className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-750 hover:text-gray-100 transition-colors group"
                  >
                    <Folder className="w-3 h-3 text-aqua-400/60 flex-shrink-0" />
                    <span className="flex-1 text-left truncate">{folder.name}</span>
                    {folder.hasChildren && (
                      <ChevronRight className="w-3 h-3 text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                    )}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setNewProjectPath(fs.path)}
                disabled={!fs.path}
                className="mt-2 w-full py-1.5 text-[11px] font-medium text-aqua-400 bg-aqua-500/10 hover:bg-aqua-500/15 border border-aqua-500/20 rounded-lg transition-colors disabled:opacity-40"
              >
                Select current folder
              </button>
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
              <label className="block text-[11px] font-medium text-gray-400 mb-1.5">Project</label>
              <select
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
