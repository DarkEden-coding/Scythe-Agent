import { useState, useRef, useEffect } from 'react';
import { User, Bot, Pencil, Check, X, RotateCw, Copy, ChevronDown, ChevronUp, Play } from 'lucide-react';
import type { Message } from '@/types';
import { Markdown } from '@/components/Markdown';
import { formatTime } from '@/utils/formatTime';
import { cn } from '@/utils/cn';

interface MessageBubbleProps {
  readonly message: Message;
  readonly onEdit?: (messageId: string, newContent: string, referencedFiles?: string[]) => void;
  readonly isProcessing?: boolean;
  readonly showContinueButton?: boolean;
  readonly onContinue?: () => void;
  readonly continueBusy?: boolean;
}

function fileLabel(path: string): string {
  const normalized = path.replace(/\\/g, '/');
  const idx = normalized.lastIndexOf('/');
  return idx >= 0 ? normalized.slice(idx + 1) : normalized;
}

function escapeMarkdownLinkLabel(text: string): string {
  return text.replace(/([\\\[\]\(\)])/g, '\\$1');
}

function buildUserMarkdownContent(content: string, referencedFiles: string[]): string {
  if (referencedFiles.length === 0) return content;
  if (/\{\{FILE:\d+\}\}/.test(content)) {
    return content.replace(FILE_PLACEHOLDER, (_, rawIndex: string) => {
      const idx = parseInt(rawIndex, 10);
      const path = referencedFiles[idx];
      if (!path) return '';
      return `[${escapeMarkdownLinkLabel(fileLabel(path))}](file-ref:${idx})`;
    });
  }

  const refsPrefix = referencedFiles
    .map((path, idx) => `[${escapeMarkdownLinkLabel(fileLabel(path))}](file-ref:${idx})`)
    .join(' ');

  return content.trim() ? `${refsPrefix}\n\n${content}` : refsPrefix;
}

/** Matches {{FILE:i}} plus any trailing stray braces (e.g. typo {{FILE:0}}}) */
const FILE_PLACEHOLDER = /\{\{FILE:(\d+)\}\}\}*/g;

function SummarizationBubble({
  summary,
  model,
}: {
  summary: string;
  model: string;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className={cn(
        'inline-block rounded-xl border border-violet-500/20 bg-violet-500/5 overflow-hidden max-w-[85%]',
        'shadow-sm hover:bg-violet-500/10 transition-colors',
      )}
    >
      <button
        type="button"
        onClick={() => setExpanded((p) => !p)}
        className="w-full flex flex-nowrap items-center justify-between gap-2 pl-4 pr-8 py-2.5 text-left text-[12px] font-medium text-violet-300 whitespace-nowrap"
      >
        <span>Image Content</span>
        {expanded ? (
          <ChevronUp className="w-3.5 h-3.5 shrink-0 text-violet-500" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5 shrink-0 text-violet-500" />
        )}
      </button>
      {expanded && (
        <div className="border-t border-violet-500/15 px-4 py-3 space-y-2">
          <p className="text-[12px] text-gray-300 whitespace-pre-wrap break-words">
            {summary}
          </p>
          <p className="text-[11px] text-violet-500/80">by {model}</p>
        </div>
      )}
    </div>
  );
}

function renderUserContent(
  content: string,
  referencedFiles: string[],
  attachments?: { data: string; mimeType: string; name?: string }[],
): React.ReactNode {
  const markdownContent = buildUserMarkdownContent(content, referencedFiles);
  const textPart = (
    <Markdown
      content={markdownContent}
      renderSpecialLink={(href, children) => {
        if (!href.startsWith('file-ref:')) return null;
        const idx = parseInt(href.slice('file-ref:'.length), 10);
        const path = referencedFiles[idx];
        if (!path) return null;
        return (
          <span
            title={path}
            className="inline-flex items-center px-2 py-0.5 rounded-md border border-aqua-500/25 bg-aqua-500/10 text-[10px] text-aqua-200 no-underline align-middle"
          >
            {children}
          </span>
        );
      }}
    />
  );

  if (!attachments?.length) return textPart;
  return (
    <div className="flex flex-col gap-2">
      {attachments.map((att, i) => (
        <img
          key={i}
          src={`data:${att.mimeType};base64,${att.data}`}
          alt={att.name ?? 'Attachment'}
          className="max-w-[280px] max-h-[200px] rounded-lg object-contain border border-gray-600/50"
        />
      ))}
      {content.trim() ? <div>{textPart}</div> : null}
    </div>
  );
}

export function MessageBubble({
  message,
  onEdit,
  isProcessing,
  showContinueButton = false,
  onContinue,
  continueBusy = false,
}: MessageBubbleProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(message.content);
  const [editReferencedFiles, setEditReferencedFiles] = useState<string[]>(message.referencedFiles ?? []);
  const [isHovered, setIsHovered] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.setSelectionRange(textareaRef.current.value.length, textareaRef.current.value.length);
    }
  }, [isEditing]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [editValue]);

  const handleEditStart = () => {
    setEditValue(message.content.replace(/\{\{FILE:\d+\}\}\}*/g, ''));
    setEditReferencedFiles(message.referencedFiles ?? []);
    setIsEditing(true);
  };

  const handleSave = () => {
    const trimmed = editValue.trim();
    const currentRefs = message.referencedFiles ?? [];
    const refsChanged = (
      editReferencedFiles.length !== currentRefs.length
      || editReferencedFiles.some((path, index) => path !== currentRefs[index])
    );
    if (!trimmed || (trimmed === message.content && !refsChanged)) {
      setIsEditing(false);
      return;
    }
    onEdit?.(message.id, trimmed, editReferencedFiles);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditValue(message.content);
    setEditReferencedFiles(message.referencedFiles ?? []);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSave();
    }
    if (e.key === 'Escape') {
      handleCancel();
    }
  };

  const handleCopy = () => {
    const refs = message.referencedFiles ?? [];
    const text = refs.length
      ? message.content.replace(/\{\{FILE:(\d+)\}\}\}*/g, (_, i) => {
          const idx = parseInt(i, 10);
          return idx >= 0 && idx < refs.length ? fileLabel(refs[idx]!) : '';
        })
      : message.content;
    void navigator.clipboard.writeText(text);
  };

  return (
    <div
      className={cn('flex min-w-0 gap-3', message.role === 'user' ? 'flex-row-reverse' : 'flex-row')}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div
        className={cn(
          'shrink-0 w-7 h-7 rounded-lg flex items-center justify-center shadow-md',
          message.role === 'user'
            ? 'bg-linear-to-br from-aqua-400 to-aqua-600'
            : 'bg-gray-750 border border-gray-600/50',
        )}
      >
        {message.role === 'user' ? (
          <User className="w-3.5 h-3.5 text-gray-950" />
        ) : (
          <Bot className="w-3.5 h-3.5 text-aqua-400" />
        )}
      </div>
      <div className={cn('flex-1 min-w-0 max-w-[85%]', message.role === 'user' ? 'text-right' : 'text-left')}>
        {isEditing ? (
          <div className="flex flex-col gap-1.5">
            <div className="w-full bg-gray-800 border border-aqua-500/40 rounded-xl text-sm transition-colors focus-within:border-aqua-500/50">
              <div className="flex flex-wrap items-center gap-1.5 px-3 py-2">
                {editReferencedFiles.map((path) => (
                  <span
                    key={path}
                    title={path}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md border border-aqua-500/30 bg-aqua-500/10 text-[11px] text-aqua-200"
                  >
                    <span className="truncate max-w-[220px]">{fileLabel(path)}</span>
                    <button
                      type="button"
                      onClick={() => setEditReferencedFiles((prev) => prev.filter((item) => item !== path))}
                      className="text-aqua-200/80 hover:text-aqua-100"
                      title="Remove file reference"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                <textarea
                  ref={textareaRef}
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={1}
                  className="min-w-[180px] flex-1 min-h-[24px] bg-transparent border-0 p-0 text-sm text-gray-200 resize-none focus:outline-none overflow-hidden"
                  style={{ height: 'auto' }}
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-1.5">
              <span className="text-[10px] text-gray-600">⌘↵ to save · Esc to cancel</span>
              <button
                onClick={handleCancel}
                className="flex items-center gap-1 px-2 py-1 text-[11px] text-gray-400 hover:text-gray-200 hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X className="w-3 h-3" />
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={!editValue.trim()}
                className="flex items-center gap-1 px-2 py-1 text-[11px] text-aqua-400 hover:text-aqua-300 hover:bg-aqua-500/10 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Check className="w-3 h-3" />
                Save
              </button>
            </div>
          </div>
        ) : (
          <>
            <div
              className={cn(
                'flex flex-col gap-2',
                message.role === 'user' ? 'items-end' : 'items-start',
              )}
            >
              <div className="relative group/bubble">
                <div
                  className={cn(
                    'inline-block max-w-full min-w-0 px-4 py-2.5 rounded-2xl text-sm shadow-md',
                    message.role === 'user'
                      ? 'bg-linear-to-br from-aqua-500/90 to-aqua-600/90 text-gray-950 rounded-br-md'
                      : 'bg-gray-800 text-gray-200 rounded-bl-md border border-gray-700/40',
                  )}
                >
                  {message.role === 'agent' ? (
                    <Markdown content={message.content} />
                  ) : (
                    <div className="min-w-0 max-w-full">
                      {renderUserContent(
                        message.content,
                        message.referencedFiles ?? [],
                        message.attachments,
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
            {message.role === 'user' &&
              message.imageSummarization &&
              message.imageSummarizationModel && (
                <div className="flex flex-row-reverse mt-2">
                  <div className="max-w-[85%] flex justify-end">
                    <SummarizationBubble
                      summary={message.imageSummarization}
                      model={message.imageSummarizationModel}
                    />
                  </div>
                </div>
              )}
            <div
              className={cn(
                'mt-1 flex items-center gap-1',
                message.role === 'user' ? 'justify-end' : 'justify-start',
              )}
            >
              <span className="text-[10px] text-gray-600">{formatTime(message.timestamp)}</span>
              {(message.role === 'user' || message.role === 'agent') && isHovered && (
                <div className="flex items-center gap-0.5">
                  <button
                    onClick={handleCopy}
                    title="Copy message"
                    className="w-5 h-5 flex items-center justify-center text-gray-600 hover:text-aqua-400 hover:bg-gray-800 rounded-md transition-colors"
                  >
                    <Copy className="w-3 h-3" />
                  </button>
                  {message.role === 'user' && onEdit && !isProcessing && (
                    <>
                      <button
                        onClick={handleEditStart}
                        title="Edit message"
                        className="w-5 h-5 flex items-center justify-center text-gray-600 hover:text-aqua-400 hover:bg-gray-800 rounded-md transition-colors"
                      >
                        <Pencil className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => onEdit?.(message.id, message.content, message.referencedFiles ?? [])}
                        title="Retry with same message"
                        className="w-5 h-5 flex items-center justify-center text-gray-600 hover:text-aqua-400 hover:bg-gray-800 rounded-md transition-colors"
                      >
                        <RotateCw className="w-3 h-3" />
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
            {message.role === 'agent' && showContinueButton && onContinue && (
              <div className="mt-2 flex justify-center">
                <button
                  type="button"
                  onClick={onContinue}
                  disabled={continueBusy}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-aqua-500/30 bg-aqua-500/10 px-2.5 py-1.5 text-[11px] font-medium text-aqua-300 transition-colors hover:bg-aqua-500/15 hover:text-aqua-200 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {continueBusy ? (
                    <div className="h-3 w-3 animate-spin rounded-full border border-aqua-300/40 border-t-aqua-300" />
                  ) : (
                    <Play className="w-3 h-3" />
                  )}
                  {continueBusy ? 'Continuing…' : 'Continue'}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
