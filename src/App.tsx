import { useState, useCallback, useRef, useEffect } from 'react';
import { Bot, Terminal, ChevronDown, Check, Loader2, GripVertical } from 'lucide-react';
import { ChatPanel } from './components/ChatPanel';
import { ActionsPanel } from './components/ActionsPanel';
import { EnhancedModelPicker } from './components/EnhancedModelPicker';
import { OpenRouterSettings } from './components/OpenRouterSettings';
import { ProviderSettingsDropdown, type ProviderId } from './components/ProviderSettingsDropdown';
import { useChatHistory, useProjects, useSettings, useAgentEvents } from './api';
import type { AgentEvent } from './api';
import type { AutoApproveRule } from './api';
import type { Checkpoint, FileEdit, Message, ReasoningBlock, ToolCall } from './types';

export function App() {
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [showNotification, setShowNotification] = useState(false);
  const [notificationMessage, setNotificationMessage] = useState('');
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [settingsProvider, setSettingsProvider] = useState<ProviderId | null>(null);
  const [processingChats, setProcessingChats] = useState<Set<string>>(new Set());

  const isProcessing = activeChatId != null && processingChats.has(activeChatId);

  // ── API hooks ──────────────────────────────────────────────────
  const chat = useChatHistory(activeChatId);
  const projectsApi = useProjects();
  const { projects, loading: projectsLoading } = projectsApi;
  const settings = useSettings();

  // Bootstrap activeChatId from first available chat when projects load
  useEffect(() => {
    if (projectsLoading) return;
    const allChats = projects.flatMap((p) => p.chats);
    const firstChatId = allChats[0]?.id ?? null;
    const currentExists = activeChatId != null && allChats.some((c) => c.id === activeChatId);
    if (!currentExists) {
      setActiveChatId(firstChatId);
    }
  }, [projectsLoading, projects, activeChatId]);

  const setProcessingChatsRef = useRef(setProcessingChats);
  setProcessingChatsRef.current = setProcessingChats;

  // ── Agent event subscription ───────────────────────────────────
  const handleAgentEvent = useCallback((event: AgentEvent) => {
    if (event.type === 'chat_title_updated') {
      projectsApi.refresh();
      return;
    }
    if (event.type === 'agent_done') {
      setProcessingChatsRef.current((prev) => {
        const next = new Set(prev);
        next.delete(event.chatId);
        return next;
      });
      return;
    }
    if (event.type === 'error') {
      const payload = event.payload as { message?: string; toolCallId?: string; source?: string };
      if (!payload.toolCallId) {
        setProcessingChatsRef.current((prev) => {
          const next = new Set(prev);
          next.delete(event.chatId);
          return next;
        });
        return;
      }
    }
    if (event.chatId !== activeChatId) return;

    const asDate = (value: string | Date): Date => (value instanceof Date ? value : new Date(value));
    const updateById = <T extends { id: string }>(items: T[], next: T) => {
      const idx = items.findIndex((item) => item.id === next.id);
      if (idx === -1) return [...items, next];
      const copy = [...items];
      copy[idx] = next;
      return copy;
    };

    switch (event.type) {
      case 'message': {
        const payload = event.payload as { message: Message };
        const message = { ...payload.message, timestamp: asDate(payload.message.timestamp) };
        chat.setMessages((prev) => updateById(prev, message));
        break;
      }
      case 'content_delta': {
        const payload = event.payload as { messageId: string; delta: string };
        chat.setMessages((prev) => {
          const idx = prev.findIndex((m) => m.id === payload.messageId);
          if (idx === -1) {
            const placeholder: Message = {
              id: payload.messageId,
              role: 'agent',
              content: payload.delta,
              timestamp: new Date(),
              checkpointId: null,
            };
            return [...prev, placeholder];
          }
          const m = prev[idx];
          const updated = { ...m, content: m.content + payload.delta };
          const copy = [...prev];
          copy[idx] = updated;
          return copy;
        });
        break;
      }
      case 'tool_call_start':
      case 'tool_call_end': {
        const payload = event.payload as { toolCall?: ToolCall & { checkpointId?: string }; toolCallId?: string; toolName?: string; input?: Record<string, unknown> };
        const toolCall = payload.toolCall ?? {
          id: payload.toolCallId ?? `tc-evt-${Date.now()}`,
          name: payload.toolName ?? 'unknown',
          status: 'pending' as const,
          input: payload.input ?? {},
          timestamp: new Date(),
          approvalRequired: false,
        };
        const tcWithTs = { ...toolCall, timestamp: asDate(toolCall.timestamp) };
        chat.setToolCalls((prev) => updateById(prev, tcWithTs));
        const cpId = (payload.toolCall as { checkpointId?: string })?.checkpointId;
        if (cpId && tcWithTs.id) {
          chat.setCheckpoints((prev) =>
            prev.map((cp) =>
              cp.id === cpId && !cp.toolCalls.includes(tcWithTs.id)
                ? { ...cp, toolCalls: [...cp.toolCalls, tcWithTs.id] }
                : cp,
            ),
          );
        }
        break;
      }
      case 'approval_required': {
        const payload = event.payload as {
          toolCall?: ToolCall & { checkpointId?: string };
          toolCallId?: string;
          toolName?: string;
          input?: Record<string, unknown>;
          description?: string;
          autoApproved?: boolean;
        };
        const toolCall = payload.toolCall ?? {
          id: payload.toolCallId ?? `tc-evt-${Date.now()}`,
          name: payload.toolName ?? 'unknown',
          status: payload.autoApproved ? ('running' as const) : ('pending' as const),
          input: payload.input ?? {},
          description: payload.description,
          approvalRequired: !payload.autoApproved,
          timestamp: new Date(),
        };
        const tcWithTs = {
          ...toolCall,
          timestamp: asDate(toolCall.timestamp),
          approvalRequired: payload.autoApproved ? false : (toolCall.approvalRequired ?? true),
          description: payload.description ?? toolCall.description,
        };
        chat.setToolCalls((prev) => updateById(prev, tcWithTs));
        const cpId = (payload.toolCall as { checkpointId?: string })?.checkpointId;
        if (cpId && tcWithTs.id) {
          chat.setCheckpoints((prev) =>
            prev.map((cp) =>
              cp.id === cpId && !cp.toolCalls.includes(tcWithTs.id)
                ? { ...cp, toolCalls: [...cp.toolCalls, tcWithTs.id] }
                : cp,
            ),
          );
        }
        break;
      }
      case 'file_edit': {
        const payload = event.payload as { fileEdit: FileEdit };
        const edit = { ...payload.fileEdit, timestamp: asDate(payload.fileEdit.timestamp) };
        chat.setFileEdits((prev) => updateById(prev, edit));
        break;
      }
      case 'reasoning_start':
      case 'reasoning_end': {
        const payload = event.payload as { reasoningBlock: ReasoningBlock };
        if (payload.reasoningBlock) {
          const block = { ...payload.reasoningBlock, timestamp: asDate(payload.reasoningBlock.timestamp) };
          chat.setReasoningBlocks((prev) => updateById(prev, block));
          const cpId = block.checkpointId;
          if (cpId && block.id) {
            chat.setCheckpoints((prev) =>
              prev.map((cp) =>
                cp.id === cpId && !(cp.reasoningBlocks ?? []).includes(block.id)
                  ? { ...cp, reasoningBlocks: [...(cp.reasoningBlocks ?? []), block.id] }
                  : cp,
              ),
            );
          }
        }
        break;
      }
      case 'reasoning_delta': {
        const payload = event.payload as { reasoningBlockId: string; delta: string };
        if (payload.reasoningBlockId && payload.delta) {
          chat.setReasoningBlocks((prev) => {
            const idx = prev.findIndex((rb) => rb.id === payload.reasoningBlockId);
            if (idx === -1) return prev;
            const copy = [...prev];
            copy[idx] = { ...copy[idx], content: copy[idx].content + payload.delta };
            return copy;
          });
        }
        break;
      }
      case 'checkpoint': {
        const payload = event.payload as { checkpoint: Checkpoint };
        const checkpoint = { ...payload.checkpoint, timestamp: asDate(payload.checkpoint.timestamp) };
        chat.setCheckpoints((prev) => updateById(prev, checkpoint));
        break;
      }
      case 'context_update': {
        const payload = event.payload as { contextItems: typeof chat.contextItems };
        chat.setContextItems(payload.contextItems);
        break;
      }
      case 'error': {
        const payload = event.payload as {
          message?: string;
          toolCallId?: string;
          toolName?: string;
        };
        if (payload.toolCallId) {
          chat.setToolCalls((prev) =>
            prev.map((tc) =>
              tc.id === payload.toolCallId
                ? { ...tc, status: 'error' as const, output: payload.message ?? tc.output }
                : tc
            )
          );
        }
        break;
      }
      default:
        break;
    }
  }, [activeChatId, chat, projectsApi]);

  useAgentEvents(activeChatId, handleAgentEvent);

  // ── Resizable panel ────────────────────────────────────────────
  const [chatWidth, setChatWidth] = useState(33.33);
  const isDragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const showToast = (message: string) => {
    setNotificationMessage(message);
    setShowNotification(true);
    setTimeout(() => setShowNotification(false), 3000);
  };

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging.current || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = (x / rect.width) * 100;
    setChatWidth(Math.min(Math.max(pct, 25), 75));
  }, []);

  const handleMouseUp = useCallback(() => {
    isDragging.current = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }, []);

  useEffect(() => {
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [handleMouseMove, handleMouseUp]);

  // ── Actions that go through the API ────────────────────────────

  const handleSendMessage = async (content: string) => {
    if (activeChatId == null) return;
    const chatIdToProcess = activeChatId;
    setProcessingChats((prev) => new Set(prev).add(chatIdToProcess));

    const res = await chat.sendMessage(content);
    if (!res.ok) {
      showToast(`Error: ${res.error}`);
      setProcessingChats((prev) => {
        const next = new Set(prev);
        next.delete(chatIdToProcess);
        return next;
      });
      return;
    }
  };

  const handleApproveCommand = async (toolCallId: string) => {
    const res = await chat.approveCommand(toolCallId);
    if (res.ok) showToast('Tool call approved');
    else showToast(`Error: ${res.error}`);
  };

  const handleRejectCommand = async (toolCallId: string) => {
    const res = await chat.rejectCommand(toolCallId);
    if (res.ok) showToast('Tool call rejected');
    else showToast(`Error: ${res.error}`);
  };

  const handleRevertToCheckpoint = async (checkpointId: string) => {
    const cp = chat.checkpoints.find((c) => c.id === checkpointId);
    const res = await chat.revertToCheckpoint(checkpointId);
    if (res.ok) showToast(`Reverted to checkpoint: ${cp?.label ?? checkpointId}`);
    else showToast(`Error: ${res.error}`);
  };

  const handleRevertFile = async (fileEditId: string) => {
    const fe = chat.fileEdits.find((f) => f.id === fileEditId);
    const res = await chat.revertFile(fileEditId);
    if (res.ok) showToast(`Reverted file: ${fe?.filePath ?? fileEditId}`);
    else showToast(`Error: ${res.error}`);
  };

  const handleSummarizeContext = async () => {
    const res = await chat.summarizeContext();
    if (res.ok) showToast('Context summarized successfully');
    else showToast(`Error: ${res.error}`);
  };

  const handleRemoveContextItem = (itemId: string) => {
    chat.removeContextItem(itemId);
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd/Ctrl + K to open model picker
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShowModelPicker(true);
      }
      // Cmd/Ctrl + , to open settings (OpenRouter for now)
      if ((e.metaKey || e.ctrlKey) && e.key === ',') {
        e.preventDefault();
        setSettingsProvider('openrouter');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSwitchChat = (chatId: string) => {
    setActiveChatId(chatId);
  };

  const handleCreateProject = async (name: string, path: string) => {
    const res = await projectsApi.createProject(name, path);
    if (!res.ok) showToast(`Error: ${res.error}`);
  };

  const handleCreateChat = async (projectId: string, title?: string) => {
    const res = await projectsApi.createChat(projectId, title);
    if (res.ok) {
      setActiveChatId(res.data.chat.id);
      showToast('Chat created');
    } else {
      showToast(`Error: ${res.error}`);
    }
  };

  const handleRenameChat = async (chatId: string, title: string) => {
    const res = await projectsApi.renameChat(chatId, title);
    if (!res.ok) showToast(`Error: ${res.error}`);
  };

  const handlePinChat = async (chatId: string, isPinned: boolean) => {
    const res = await projectsApi.pinChat(chatId, isPinned);
    if (!res.ok) showToast(`Error: ${res.error}`);
  };

  const handleDeleteChat = async (chatId: string) => {
    const res = await projectsApi.deleteChat(chatId);
    if (res.ok) {
      if (chatId === activeChatId) {
        setActiveChatId(res.data.fallbackChatId ?? null);
      }
      showToast('Chat deleted');
    } else {
      showToast(`Error: ${res.error}`);
    }
  };

  const handleReorderProjects = async (projectIds: string[]) => {
    const res = await projectsApi.reorderProjects(projectIds);
    if (!res.ok) showToast(`Error: ${res.error}`);
  };

  const handleReorderChats = async (projectId: string, chatIds: string[]) => {
    const res = await projectsApi.reorderChats(projectId, chatIds);
    if (!res.ok) showToast(`Error: ${res.error}`);
  };

  const handleDeleteProject = async (projectId: string) => {
    const project = projects.find((p) => p.id === projectId);
    const hadActiveChat = project?.chats.some((c) => c.id === activeChatId);
    const res = await projectsApi.deleteProject(projectId);
    if (res.ok) {
      if (hadActiveChat) setActiveChatId(null);
      showToast('Project deleted');
    } else {
      showToast(`Error: ${res.error}`);
    }
  };

  const handleUpdateAutoApproveRules = async (rules: Omit<AutoApproveRule, 'id' | 'createdAt'>[]) => {
    const res = await settings.updateAutoApproveRules(rules);
    if (!res.ok) {
      showToast(`Error: ${res.error}`);
    }
  };

  // ── Loading state ──────────────────────────────────────────────
  const currentProject =
    activeChatId != null
      ? projects.find((p) => p.chats.some((c) => c.id === activeChatId))
      : undefined;
  const currentProjectChats = [...(currentProject?.chats ?? [])].sort((a, b) => {
    if (a.isPinned && !b.isPinned) return -1;
    if (!a.isPinned && b.isPinned) return 1;
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  });
  const headerChatsRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const [dragHeaderChatIndex, setDragHeaderChatIndex] = useState<number | null>(null);
  const [dragOverHeaderChatIndex, setDragOverHeaderChatIndex] = useState<number | null>(null);

  const updateScrollState = useCallback(() => {
    const el = headerChatsRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 0);
    setCanScrollRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 1);
  }, []);

  useEffect(() => {
    updateScrollState();
    const el = headerChatsRef.current;
    if (!el) return;
    const ro = new ResizeObserver(updateScrollState);
    ro.observe(el);
    el.addEventListener('scroll', updateScrollState);
    return () => {
      ro.disconnect();
      el.removeEventListener('scroll', updateScrollState);
    };
  }, [updateScrollState, currentProjectChats.length]);

  useEffect(() => {
    const el = headerChatsRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => {
      if (e.deltaY === 0) return;
      e.preventDefault();
      el.scrollLeft += e.deltaY;
    };
    el.addEventListener('wheel', handler, { passive: false });
    return () => el.removeEventListener('wheel', handler);
  }, [currentProjectChats.length, chat.loading, projectsLoading]);

  const handleHeaderChatDrop = useCallback(
    (dropIndex: number) => {
      if (!currentProject || dragHeaderChatIndex === null || dragHeaderChatIndex === dropIndex) return;
      const ids = currentProjectChats.map((c) => c.id);
      const [removed] = ids.splice(dragHeaderChatIndex, 1);
      ids.splice(dropIndex, 0, removed);
      handleReorderChats(currentProject.id, ids);
      setDragHeaderChatIndex(null);
      setDragOverHeaderChatIndex(null);
    },
    [currentProject, currentProjectChats, dragHeaderChatIndex, handleReorderChats],
  );

  if (chat.loading || projectsLoading) {
    return (
      <div className="h-screen w-screen bg-gray-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-aqua-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-gray-400">Loading…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen bg-gray-950 text-white flex flex-col overflow-hidden">
      {/* ── Top Bar ─────────────────────────────────────────────── */}
      <header className="flex items-center justify-between gap-3 px-5 py-2.5 bg-gray-900/80 border-b border-gray-700/30 min-h-0">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className="flex items-center justify-center w-8 h-8 bg-gradient-to-br from-aqua-400 to-aqua-600 rounded-xl shadow-lg shadow-aqua-500/20 flex-shrink-0">
            <Bot className="w-4.5 h-4.5 text-gray-950" />
          </div>
          <h1 className="text-sm font-semibold text-gray-200 flex-shrink-0">Agentic Coder</h1>
          <div className="flex items-center gap-1.5 min-w-0 flex-1 overflow-hidden">
            <div className="flex items-center gap-0 min-w-0 flex-1 rounded-lg border border-gray-700/50 bg-gray-800/40 px-2 py-1.5">
              {canScrollLeft && currentProjectChats.length > 0 && (
                <span className="flex-shrink-0 text-gray-500 text-xs">…</span>
              )}
              <div
                ref={headerChatsRef}
                className="flex items-center gap-2 overflow-x-auto overflow-y-hidden pb-1.5"
              >
                {currentProjectChats.map((c, ci) => {
                  const processing = processingChats.has(c.id);
                  const isDragging = dragHeaderChatIndex === ci;
                  const isDropTarget = dragOverHeaderChatIndex === ci && dragHeaderChatIndex !== ci;
                  return (
                    <button
                      type="button"
                      key={c.id}
                      draggable
                      onDragStart={(e) => {
                        setDragHeaderChatIndex(ci);
                        e.dataTransfer.effectAllowed = 'move';
                      }}
                      onDragEnd={() => {
                        setDragHeaderChatIndex(null);
                        setDragOverHeaderChatIndex(null);
                      }}
                      onDragOver={(e) => {
                        e.preventDefault();
                        if (dragHeaderChatIndex !== null && ci !== dragHeaderChatIndex)
                          setDragOverHeaderChatIndex(ci);
                      }}
                      onDrop={(e) => {
                        e.preventDefault();
                        handleHeaderChatDrop(ci);
                      }}
                      onClick={() => handleSwitchChat(c.id)}
                      className={`flex items-center gap-1.5 flex-shrink-0 px-2 py-1 rounded text-xs transition-colors whitespace-nowrap cursor-grab active:cursor-grabbing ${
                        c.id === activeChatId
                          ? 'bg-aqua-500/30 text-aqua-200 border border-aqua-400/40'
                          : 'bg-gray-800/50 text-gray-400 border border-gray-700/40 hover:bg-gray-750 hover:text-gray-300'
                      } ${isDragging ? 'opacity-40' : ''} ${isDropTarget ? 'ring-1 ring-aqua-400/60' : ''}`}
                      title={c.title}
                    >
                      <GripVertical className="w-3 h-3 shrink-0 text-gray-500 opacity-60" />
                      {processing ? (
                        <Loader2 className="w-3 h-3 shrink-0 animate-spin text-aqua-400" />
                      ) : (
                        <Check className="w-3 h-3 shrink-0 text-green-500/80" />
                      )}
                      <span className="truncate max-w-[120px]">
                        {c.isPinned ? '[Pinned] ' : ''}
                        {c.title || 'Untitled'}
                      </span>
                    </button>
                  );
                })}
              </div>
              {canScrollRight && currentProjectChats.length > 0 && (
                <span className="flex-shrink-0 text-gray-500 text-xs">…</span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Model picker */}
          <button
            onClick={() => setShowModelPicker(true)}
            onMouseEnter={() => settings.prefetchSettings()}
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-800/60 rounded-xl border border-gray-700/40 shadow-sm hover:bg-gray-750 transition-colors"
            title="Change model (⌘K)"
          >
            <Terminal className="w-3.5 h-3.5 text-aqua-400" />
            <span className="text-xs text-gray-400">{settings.currentModel}</span>
            <ChevronDown className="w-3 h-3 text-gray-500" />
          </button>

          <ProviderSettingsDropdown onSelectProvider={setSettingsProvider} />
        </div>
      </header>

      {/* ── Main Content ────────────────────────────────────────── */}
      <div ref={containerRef} className="flex-1 flex gap-0 p-3 overflow-hidden">
        {/* Left Panel – Chat */}
        <div className="flex flex-col overflow-hidden" style={{ width: `${chatWidth}%` }}>
          <ChatPanel
            messages={chat.messages}
            checkpoints={chat.checkpoints}
            onRevert={handleRevertToCheckpoint}
            contextItems={chat.contextItems}
            maxTokens={chat.maxTokens}
            onSummarize={handleSummarizeContext}
            onRemoveContextItem={handleRemoveContextItem}
            onSendMessage={handleSendMessage}
            projects={projects}
            activeChatId={activeChatId}
            onSwitchChat={handleSwitchChat}
            isProcessing={isProcessing}
            onCreateProject={handleCreateProject}
            onCreateChat={handleCreateChat}
            onRenameChat={handleRenameChat}
            onPinChat={handlePinChat}
            onDeleteChat={handleDeleteChat}
            onReorderProjects={handleReorderProjects}
            onReorderChats={handleReorderChats}
            onDeleteProject={handleDeleteProject}
          />
        </div>

        {/* Resize Handle */}
        <div
          className="resize-handle group flex items-center justify-center w-3 flex-shrink-0 cursor-col-resize z-10"
          onMouseDown={handleMouseDown}
        >
          <div className="w-[3px] h-12 rounded-full bg-gray-700/50 group-hover:bg-aqua-400/50 group-active:bg-aqua-400/80 transition-colors" />
        </div>

        {/* Right Panel – Agent Activity */}
        <div className="overflow-hidden" style={{ width: `${100 - chatWidth}%` }}>
          <ActionsPanel
            toolCalls={chat.toolCalls}
            fileEdits={chat.fileEdits}
            checkpoints={chat.checkpoints}
            reasoningBlocks={chat.reasoningBlocks}
            onRevertFile={handleRevertFile}
            onRevertCheckpoint={handleRevertToCheckpoint}
            onApproveCommand={handleApproveCommand}
            onRejectCommand={handleRejectCommand}
            autoApproveRules={settings.autoApproveRules}
            onUpdateAutoApproveRules={handleUpdateAutoApproveRules}
          />
        </div>
      </div>

      {/* Toast */}
      {showNotification && (
        <div className="fixed bottom-4 right-4 px-4 py-3 bg-gray-800 border border-gray-700/50 rounded-xl shadow-2xl shadow-black/50 animate-in slide-in-from-bottom-2 fade-in duration-200">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-aqua-400" />
            <p className="text-sm text-gray-200">{notificationMessage}</p>
          </div>
        </div>
      )}

      {/* Modals — always mounted so opening is instant (no mount delay) */}
      <EnhancedModelPicker
        visible={showModelPicker}
        onClose={() => setShowModelPicker(false)}
        currentModel={settings.currentModel}
        modelsByProvider={settings.modelsByProvider}
        modelMetadata={settings.modelMetadata}
        loading={settings.loading}
        changeModel={settings.changeModel}
      />
      <OpenRouterSettings
        visible={settingsProvider === 'openrouter'}
        onClose={() => setSettingsProvider(null)}
      />
    </div>
  );
}
