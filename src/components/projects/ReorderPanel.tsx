import { ChevronRight, ChevronUp, ChevronDown, GripVertical, Folder, MessageSquare } from 'lucide-react';
import type { Project } from '@/types';
import { cn } from '@/utils/cn';

interface ReorderPanelProps {
  projects: Project[];
  dragProjectIndex: number | null;
  dragOverProjectIndex: number | null;
  dragChatKey: { projectId: string; chatIndex: number } | null;
  dragOverChatIndex: number | null;
  reorderExpandedProject: string | null;
  onProjectDragStart: (e: React.DragEvent, index: number) => void;
  onProjectDragEnd: (e: React.DragEvent) => void;
  onProjectDrop: (e: React.DragEvent, dropIndex: number) => void;
  onProjectDragOver: (e: React.DragEvent, index: number) => void;
  onProjectDragLeave: () => void;
  onChatDragStart: (e: React.DragEvent, projectId: string, chatIndex: number) => void;
  onChatDragEnd: (e: React.DragEvent) => void;
  onChatDragOver: (e: React.DragEvent, chatIndex: number) => void;
  onChatDrop: (e: React.DragEvent, projectId: string, dropIndex: number) => void;
  onToggleReorderExpand: (projectId: string) => void;
  onMoveProject: (index: number, direction: 'up' | 'down') => void;
  onMoveChat: (projectId: string, chatIndex: number, direction: 'up' | 'down') => void;
}

export function ReorderPanel({
  projects,
  dragProjectIndex,
  dragOverProjectIndex,
  dragChatKey,
  dragOverChatIndex,
  reorderExpandedProject,
  onProjectDragStart,
  onProjectDragEnd,
  onProjectDrop,
  onProjectDragOver,
  onProjectDragLeave,
  onChatDragStart,
  onChatDragEnd,
  onChatDragOver,
  onChatDrop,
  onToggleReorderExpand,
  onMoveProject,
  onMoveChat,
}: ReorderPanelProps) {
  return (
    <>
      {projects.map((project, pi) => (
        <div
          key={project.id}
          draggable
          onDragStart={(e) => onProjectDragStart(e, pi)}
          onDragEnd={onProjectDragEnd}
          onDragOver={(e) => onProjectDragOver(e, pi)}
          onDrop={(e) => onProjectDrop(e, pi)}
          onDragLeave={onProjectDragLeave}
          className={cn(
            'rounded-xl border mb-1.5 overflow-hidden transition-all duration-150',
            dragOverProjectIndex === pi
              ? 'border-aqua-400/60 bg-aqua-500/5 shadow-md shadow-aqua-500/10'
              : 'border-gray-700/40 bg-gray-800/30',
            dragProjectIndex === pi && 'opacity-40',
          )}
        >
          <div className="flex items-center gap-2 px-3 py-2.5 group">
            <div className="cursor-grab active:cursor-grabbing p-0.5 rounded hover:bg-gray-700/50 transition-colors">
              <GripVertical className="w-3.5 h-3.5 text-gray-500 hover:text-aqua-400 transition-colors" />
            </div>
            <div className="flex items-center justify-center w-6 h-6 bg-gray-800 rounded-md border border-gray-700/50">
              <Folder className="w-3 h-3 text-aqua-400/80" />
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-sm font-medium text-gray-200 truncate block">{project.name}</span>
              <span className="text-[10px] text-gray-500 font-mono truncate block">{project.path}</span>
            </div>
            <div className="flex items-center gap-0.5 flex-shrink-0">
              {project.chats.length > 0 && (
                <button
                  onClick={() => onToggleReorderExpand(project.id)}
                  className={cn(
                    'p-1 rounded-md text-gray-500 hover:text-gray-300 hover:bg-gray-700/50 transition-colors',
                    reorderExpandedProject === project.id && 'text-aqua-400',
                  )}
                >
                  <ChevronRight
                    className={cn('w-3 h-3 transition-transform', reorderExpandedProject === project.id && 'rotate-90')}
                  />
                </button>
              )}
              <button
                onClick={() => onMoveProject(pi, 'up')}
                disabled={pi === 0}
                className="p-1 rounded-md text-gray-500 hover:text-gray-200 hover:bg-gray-700/50 disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronUp className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => onMoveProject(pi, 'down')}
                disabled={pi === projects.length - 1}
                className="p-1 rounded-md text-gray-500 hover:text-gray-200 hover:bg-gray-700/50 disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronDown className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
          {reorderExpandedProject === project.id && project.chats.length > 0 && (
            <div className="mx-2 mb-2 ml-7 space-y-0.5 border-l-2 border-gray-700/40 pl-2">
              {project.chats.map((chat, ci) => (
                <div
                  key={chat.id}
                  draggable
                  onDragStart={(e) => onChatDragStart(e, project.id, ci)}
                  onDragEnd={onChatDragEnd}
                  onDragOver={(e) => onChatDragOver(e, ci)}
                  onDrop={(e) => onChatDrop(e, project.id, ci)}
                  className={cn(
                    'flex items-center gap-2 px-2.5 py-1.5 rounded-lg transition-all duration-150',
                    dragOverChatIndex === ci && dragChatKey?.projectId === project.id
                      ? 'bg-aqua-500/10 border border-aqua-400/40 shadow-sm shadow-aqua-500/10'
                      : 'bg-gray-800/40 border border-transparent',
                    dragChatKey?.projectId === project.id && dragChatKey?.chatIndex === ci && 'opacity-40',
                  )}
                >
                  <div className="cursor-grab active:cursor-grabbing p-0.5 rounded hover:bg-gray-700/50 transition-colors">
                    <GripVertical className="w-3 h-3 text-gray-500 hover:text-aqua-400 transition-colors" />
                  </div>
                  <MessageSquare className="w-3 h-3 text-gray-500 flex-shrink-0" />
                  <span className="text-xs text-gray-300 truncate flex-1">{chat.title}</span>
                  <div className="flex items-center gap-0.5 flex-shrink-0">
                    <button
                      onClick={() => onMoveChat(project.id, ci, 'up')}
                      disabled={ci === 0}
                      className="p-0.5 rounded text-gray-500 hover:text-gray-200 hover:bg-gray-700/50 disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
                    >
                      <ChevronUp className="w-3 h-3" />
                    </button>
                    <button
                      onClick={() => onMoveChat(project.id, ci, 'down')}
                      disabled={ci === project.chats.length - 1}
                      className="p-0.5 rounded text-gray-500 hover:text-gray-200 hover:bg-gray-700/50 disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
                    >
                      <ChevronDown className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </>
  );
}
