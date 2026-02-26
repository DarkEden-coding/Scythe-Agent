import { RotateCcw, Bot, MessageSquare, Database } from 'lucide-react';
import type { Message, Checkpoint, VerificationIssues, ObservationData } from '@/types';
import { MessageBubble } from './MessageBubble';
import { VerificationIssuesBanner } from './VerificationIssuesBanner';
import { ObservationMessage } from './ObservationMessage';

interface MessageListProps {
  readonly messages: Message[];
  readonly activeChatId: string | null;
  readonly isProcessing: boolean;
  readonly onRevert: (checkpointId: string) => void;
  readonly onEditMessage?: (messageId: string, newContent: string, referencedFiles?: string[]) => void;
  readonly getCheckpointForMessage: (messageId: string) => Checkpoint | undefined;
  readonly verificationIssues?: Record<string, VerificationIssues>;
  readonly observation?: ObservationData | null;
  readonly observations?: ObservationData[];
  readonly showObservationsInChat?: boolean;
}

function ObservationSwitchMessage({
  generation,
  triggerTokens,
}: {
  generation?: number;
  triggerTokens?: number;
}) {
  const triggerTokensLabel =
    typeof triggerTokens === 'number' && Number.isFinite(triggerTokens) && triggerTokens > 0
      ? ` · trigger tokens: ${triggerTokens.toLocaleString()}`
      : '';
  return (
    <div className="my-2 mx-2">
      <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 overflow-hidden">
        <div className="w-full flex items-center gap-2 px-4 py-2.5">
          <Database className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
          <span className="text-xs font-medium text-cyan-300 flex-1">
            Switched earlier chat history to observations
            {generation !== undefined ? ` · Gen ${generation}` : ''}
            {triggerTokensLabel}
          </span>
        </div>
      </div>
    </div>
  );
}

export function MessageList({
  messages,
  activeChatId,
  isProcessing,
  onRevert,
  onEditMessage,
  getCheckpointForMessage,
  verificationIssues = {},
  observation = null,
  observations = [],
  showObservationsInChat = false,
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

  const timelineSource = observations.length > 0
    ? observations
    : (observation ? [observation] : []);
  const observationTimeline = showObservationsInChat
    ? timelineSource.filter((item) => item.hasObservations && !!item.content)
    : [];
  const messageIdSet = new Set(messages.map((m) => m.id));
  const observationsByMessageId = new Map<string, ObservationData[]>();
  const unanchoredObservations: ObservationData[] = [];
  for (const item of observationTimeline) {
    const waterline = item.observedUpToMessageId;
    if (waterline && messageIdSet.has(waterline)) {
      const existing = observationsByMessageId.get(waterline) ?? [];
      existing.push(item);
      observationsByMessageId.set(waterline, existing);
    } else {
      unanchoredObservations.push(item);
    }
  }
  let prevCheckpointId: string | null = null;

  return (
    <>
      {messages.map((message, index) => {
        const checkpoint = message.checkpointId ? getCheckpointForMessage(message.id) : null;
        const prevCpId = prevCheckpointId;
        if (checkpoint) {
          prevCheckpointId = checkpoint.id;
        }
        const verificationBanner =
          checkpoint && prevCpId && verificationIssues[prevCpId];

        return (
          <div key={message.id}>
            <div className="space-y-2">
              {verificationBanner && (
                <div className="py-1">
                  <VerificationIssuesBanner
                    issues={verificationIssues[prevCpId]}
                    isActive={false}
                  />
                </div>
              )}
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
              <MessageBubble message={message} onEdit={onEditMessage} isProcessing={isProcessing} />
            </div>
            {(observationsByMessageId.get(message.id) ?? []).map((item, itemIndex) => (
              <div key={`${item.id ?? item.timestamp ?? 'obs'}-${itemIndex}`}>
                {item.source !== 'buffered' && (
                  <ObservationSwitchMessage
                    generation={item.generation}
                    triggerTokens={item.triggerTokenCount ?? item.tokenCount}
                  />
                )}
                <ObservationMessage observation={item} />
              </div>
            ))}
          </div>
        );
      })}
      {unanchoredObservations.map((item, itemIndex) => (
        <div key={`tail-${item.id ?? item.timestamp ?? 'obs'}-${itemIndex}`}>
          {item.source !== 'buffered' && (
            <ObservationSwitchMessage
              generation={item.generation}
              triggerTokens={item.triggerTokenCount ?? item.tokenCount}
            />
          )}
          <ObservationMessage observation={item} />
        </div>
      ))}
      {isProcessing && (
        <div className="flex gap-3 pt-2">
          <div className="shrink-0 w-7 h-7 rounded-lg flex items-center justify-center bg-gray-750 border border-gray-600/50 shadow-md">
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
