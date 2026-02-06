import { useState, useCallback, useRef, useEffect } from 'react';
import { Bot, Settings, Moon, Sun, Terminal, ChevronDown } from 'lucide-react';
import { ChatPanel } from './components/ChatPanel';
import { ActionsPanel } from './components/ActionsPanel';
import { useChatHistory, useProjects, useSettings, useAgentEvents } from './api';
import type { AgentEvent } from './api';
import type { AutoApproveRule } from './api';
import type { Checkpoint, FileEdit, Message, ReasoningBlock, ToolCall } from './types';

export function App() {
  const [activeChatId, setActiveChatId] = useState('chat-1');
  const [darkMode, setDarkMode] = useState(true);
  const [showNotification, setShowNotification] = useState(false);
  const [notificationMessage, setNotificationMessage] = useState('');
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [processingChats, setProcessingChats] = useState<Set<string>>(new Set());

  const isProcessing = processingChats.has(activeChatId);

  // ── API hooks ──────────────────────────────────────────────────
  const chat = useChatHistory(activeChatId);
  const projectsApi = useProjects();
  const { projects, loading: projectsLoading } = projectsApi;
  const settings = useSettings();

  // ── Agent event subscription ───────────────────────────────────
  const handleAgentEvent = useCallback((event: AgentEvent) => {
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
      case 'tool_call_start':
      case 'tool_call_end': {
        const payload = event.payload as { toolCall?: ToolCall; toolCallId?: string; toolName?: string; input?: Record<string, unknown> };
        const toolCall = payload.toolCall ?? {
          id: payload.toolCallId ?? `tc-evt-${Date.now()}`,
          name: payload.toolName ?? 'unknown',
          status: 'pending' as const,
          input: payload.input ?? {},
          timestamp: new Date(),
          approvalRequired: false,
        };
        chat.setToolCalls((prev) => updateById(prev, { ...toolCall, timestamp: asDate(toolCall.timestamp) }));
        break;
      }
      case 'approval_required': {
        const payload = event.payload as {
          toolCall?: ToolCall;
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
        chat.setToolCalls((prev) =>
          updateById(prev, {
            ...toolCall,
            timestamp: asDate(toolCall.timestamp),
            approvalRequired: payload.autoApproved ? false : (toolCall.approvalRequired ?? true),
            description: payload.description ?? toolCall.description,
          }),
        );
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
        const payload = event.payload as { message?: string };
        showToast(payload.message ?? 'Agent error');
        break;
      }
      default:
        break;
    }
  }, [activeChatId, chat]);

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
    // Mark this chat as processing
    setProcessingChats((prev) => new Set(prev).add(activeChatId));

    const res = await chat.sendMessage(content);
    if (!res.ok) {
      showToast(`Error: ${res.error}`);
      setProcessingChats((prev) => {
        const next = new Set(prev);
        next.delete(activeChatId);
        return next;
      });
      return;
    }

    setProcessingChats((prev) => {
      const next = new Set(prev);
      next.delete(activeChatId);
      return next;
    });
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

  const handleChangeModel = async (model: string) => {
    const res = await settings.changeModel(model);
    if (res.ok) {
      chat.setModel(res.data.model);
      chat.setMaxTokens(res.data.contextLimit);
      showToast(`Switched to ${res.data.model}`);
    }
    setShowModelPicker(false);
  };

  const handleSwitchChat = (chatId: string) => {
    setActiveChatId(chatId);
  };

  const handleCreateProject = async (name: string, path: string) => {
    const res = await projectsApi.createProject(name, path);
    if (!res.ok) showToast(`Error: ${res.error}`);
  };

  const handleCreateChat = async (projectId: string, title: string) => {
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
      if (chatId === activeChatId && res.data.fallbackChatId) {
        setActiveChatId(res.data.fallbackChatId);
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

  const handleUpdateAutoApproveRules = async (rules: Omit<AutoApproveRule, 'id' | 'createdAt'>[]) => {
    const res = await settings.updateAutoApproveRules(rules);
    if (!res.ok) {
      showToast(`Error: ${res.error}`);
    }
  };

  // ── Loading state ──────────────────────────────────────────────
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
      <header className="flex items-center justify-between px-5 py-2.5 bg-gray-900/80 border-b border-gray-700/30">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-8 h-8 bg-gradient-to-br from-aqua-400 to-aqua-600 rounded-xl shadow-lg shadow-aqua-500/20">
            <Bot className="w-4.5 h-4.5 text-gray-950" />
          </div>
          <h1 className="text-sm font-semibold text-gray-200">Agentic Coder</h1>
        </div>

        <div className="flex items-center gap-2">
          {/* Model picker */}
          <div className="relative">
            <button
              onClick={() => setShowModelPicker(!showModelPicker)}
              className="flex items-center gap-2 px-3 py-1.5 bg-gray-800/60 rounded-xl border border-gray-700/40 shadow-sm hover:bg-gray-750 transition-colors"
            >
              <Terminal className="w-3.5 h-3.5 text-aqua-400" />
              <span className="text-xs text-gray-400">{chat.model}</span>
              <ChevronDown className="w-3 h-3 text-gray-500" />
            </button>

            {showModelPicker && (
              <div className="absolute top-full right-0 mt-2 w-52 bg-gray-850 border border-gray-700/60 rounded-xl shadow-2xl shadow-black/40 py-1 z-50 animate-dropdown">
                {settings.availableModels.map((m) => (
                  <button
                    key={m}
                    onClick={() => handleChangeModel(m)}
                    className={`w-full text-left px-3 py-2 text-xs transition-colors ${
                      m === chat.model
                        ? 'text-aqua-400 bg-aqua-500/10'
                        : 'text-gray-300 hover:bg-gray-800/60'
                    }`}
                  >
                    {m}
                    {m === chat.model && (
                      <span className="ml-2 text-[10px] text-aqua-400/60">active</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={() => setDarkMode(!darkMode)}
            className="p-2 text-gray-500 hover:text-gray-300 hover:bg-gray-800 rounded-xl transition-colors"
          >
            {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>

          <button className="p-2 text-gray-500 hover:text-gray-300 hover:bg-gray-800 rounded-xl transition-colors">
            <Settings className="w-4 h-4" />
          </button>
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
    </div>
  );
}
