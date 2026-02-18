import { RotateCcw, Bot, MessageSquare } from 'lucide-react';
import type { Message, Checkpoint } from '@/types';
import { MessageBubble } from './MessageBubble';
interface MessageListProps {
  messages: Message[];
  activeChatId: string | null;
  isProcessing: boolean;
  onRevert: (checkpointId: string) => void;
  getCheckpointForMessage: (messageId: string) => Checkpoint | undefined;
}

export function MessageList({
  messages,
  activeChatId,
  isProcessing,
  onRevert,
  getCheckpointForMessage,
}: MessageListProps) {
  if (!activeChatId) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <MessageSquare className="w-12 h-12 text-gray-600 mb-3" />
        <p className="text-sm text-gray-400 mb-1">No chats yet.</p>
        <p className="text-xs text-gray-500">Create a project or chat to get started.</p>
      </div>
    );
  }

  return (
    <>
      {messages.map((message) => {
        const checkpoint = message.checkpointId ? getCheckpointForMessage(message.id) : null;
        return (
          <div key={message.id} className="space-y-2">
            {checkpoint && (
              <div className="flex items-center gap-2 py-2">
                <div className="flex-1 h-px bg-gray-700/50" />
                <div className="flex items-center gap-2 px-2.5 py-1 bg-gray-800 rounded-full border border-gray-700/50 shadow-sm">
                  <div className="w-1.5 h-1.5 rounded-full bg-aqua-400/60" />
                  <span className="text-[11px] text-gray-400">{checkpoint.label}</span>
                  <button
                    onClick={() => onRevert(checkpoint.id)}
                    className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] text-amber-400 hover:text-amber-300 hover:bg-gray-700 rounded transition-colors"
                    title="Revert to this checkpoint"
                  >
                    <RotateCcw className="w-2.5 h-2.5" />
                  </button>
                </div>
                <div className="flex-1 h-px bg-gray-700/50" />
              </div>
            )}
            <MessageBubble message={message} />
          </div>
        );
      })}
      {isProcessing && (
        <div className="flex gap-3 pt-2">
          <div className="flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center bg-gray-750 border border-gray-600/50 shadow-md">
            <Bot className="w-3.5 h-3.5 text-aqua-400" />
          </div>
          <div className="flex items-center gap-2.5 px-4 py-2.5 bg-gray-800 rounded-2xl rounded-bl-md border border-gray-700/40 shadow-md">
            <div className="w-4 h-4 rounded-full border-2 border-gray-600 border-t-gray-300 animate-spin" />
            <span className="text-xs text-gray-400">Agent is thinking</span>
          </div>
        </div>
      )}
    </>
  );
}
