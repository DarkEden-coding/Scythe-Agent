import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FileText, Send, Square, X } from 'lucide-react';
import { api as defaultApi } from '@/api/client';
import { cn } from '@/utils/cn';

const IMAGE_MIMES = new Set(['image/png', 'image/jpeg', 'image/gif', 'image/webp']);
const MAX_ATTACHMENT_SIZE_MB = 8;

interface ImageAttachment {
  data: string;
  mimeType: string;
  name?: string;
}

interface MessageInputProps {
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly referencedFiles?: string[];
  readonly onReferencedFilesChange?: (paths: string[]) => void;
  readonly attachments?: ImageAttachment[];
  readonly onAttachmentsChange?: (attachments: ImageAttachment[]) => void;
  readonly onSubmit: () => void;
  readonly onCancel?: () => void;
  readonly composeMode?: 'default' | 'planning';
  readonly onComposeModeChange?: (mode: 'default' | 'planning') => void;
  readonly activeChatId: string | null;
  readonly activeProjectPath?: string | null;
  readonly disabled?: boolean;
  readonly isProcessing?: boolean;
}

interface IndexedProjectFile {
  name: string;
  path: string;
  relativePath: string;
  nameLower: string;
  relativePathLower: string;
}

interface MentionContext {
  start: number;
  cursor: number;
  query: string;
}

type Segment = { type: 'text'; value: string } | { type: 'chip'; path: string };

/** Matches {{FILE:i}} plus any trailing stray braces */
const FILE_PLACEHOLDER = /\{\{FILE:(\d+)\}\}\}*/g;

function segmentsToValue(segments: Segment[]): string {
  let chipIndex = 0;
  return segments
    .map((s) => (s.type === 'text' ? s.value : `{{FILE:${chipIndex++}}}`))
    .join('');
}

function segmentsToRefs(segments: Segment[]): string[] {
  return segments.filter((s): s is { type: 'chip'; path: string } => s.type === 'chip').map((s) => s.path);
}

function parseContentWithPlaceholders(content: string, refs: string[]): Segment[] {
  const segments: Segment[] = [];
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  const pattern = new RegExp(FILE_PLACEHOLDER.source, 'g');
  while ((m = pattern.exec(content)) !== null) {
    if (m.index > lastIndex) segments.push({ type: 'text', value: content.slice(lastIndex, m.index) });
    const idx = parseInt(m[1] ?? '0', 10);
    if (idx >= 0 && idx < refs.length) segments.push({ type: 'chip', path: refs[idx]! });
    lastIndex = m.index + (m[0]?.length ?? 0);
  }
  if (lastIndex < content.length) segments.push({ type: 'text', value: content.slice(lastIndex) });
  return segments.length ? segments : [{ type: 'text', value: content }];
}

function valueAndRefsToSegments(value: string, refs: string[]): Segment[] {
  if (refs.length === 0) return [{ type: 'text', value }];
  if (/\{\{FILE:\d+\}\}/.test(value)) return parseContentWithPlaceholders(value, refs);
  return [...refs.map((path) => ({ type: 'chip' as const, path })), { type: 'text' as const, value }];
}

function fileLabel(path: string): string {
  const n = path.replace(/\\/g, '/');
  const i = n.lastIndexOf('/');
  return i >= 0 ? n.slice(i + 1) : n;
}

const IGNORED_DIRECTORY_NAMES = new Set([
  '.git',
  '.hg',
  '.svn',
  '.venv',
  'venv',
  'env',
  '__pycache__',
  'node_modules',
  'dist',
  'build',
  '.mypy_cache',
  '.pytest_cache',
  '.ruff_cache',
  '.next',
  '.turbo',
  '.cache',
  '.idea',
  '.vscode',
].map((name) => name.toLowerCase()));

const MAX_INDEXED_FILES = 10_000;
const MAX_VISIBLE_MENTIONS = 8;

const fileIndexCache = new Map<string, IndexedProjectFile[]>();
const inFlightIndexBuilds = new Map<string, Promise<IndexedProjectFile[]>>();

function normalizePath(path: string): string {
  return path.replace(/\\/g, '/').replace(/\/+$/, '');
}

function toRelativePath(rootPath: string, fullPath: string): string {
  const root = normalizePath(rootPath);
  const full = normalizePath(fullPath);
  if (full === root) return '';
  const prefix = `${root}/`;
  return full.startsWith(prefix) ? full.slice(prefix.length) : fullPath;
}

function shouldIgnoreDirectory(name: string): boolean {
  return IGNORED_DIRECTORY_NAMES.has(name.toLowerCase());
}

async function buildProjectFileIndex(projectPath: string): Promise<IndexedProjectFile[]> {
  const files: IndexedProjectFile[] = [];
  const toVisit: string[] = [projectPath];
  const visited = new Set<string>();

  while (toVisit.length > 0 && files.length < MAX_INDEXED_FILES) {
    const currentDir = toVisit.pop();
    if (!currentDir || visited.has(currentDir)) continue;
    visited.add(currentDir);

    const response = await defaultApi.getFsChildren(currentDir);
    if (!response.ok) continue;

    for (const child of response.data.children) {
      if (child.kind === 'directory') {
        if (shouldIgnoreDirectory(child.name)) continue;
        toVisit.push(child.path);
        continue;
      }

      const relativePath = toRelativePath(projectPath, child.path);
      files.push({
        name: child.name,
        path: child.path,
        relativePath,
        nameLower: child.name.toLowerCase(),
        relativePathLower: relativePath.toLowerCase(),
      });

      if (files.length >= MAX_INDEXED_FILES) break;
    }
  }

  files.sort((a, b) => a.relativePathLower.localeCompare(b.relativePathLower));
  return files;
}

async function getProjectFileIndex(projectPath: string): Promise<IndexedProjectFile[]> {
  const cached = fileIndexCache.get(projectPath);
  if (cached) return cached;

  const inFlight = inFlightIndexBuilds.get(projectPath);
  if (inFlight) return inFlight;

  const promise = buildProjectFileIndex(projectPath)
    .then((files) => {
      fileIndexCache.set(projectPath, files);
      return files;
    })
    .finally(() => {
      inFlightIndexBuilds.delete(projectPath);
    });

  inFlightIndexBuilds.set(projectPath, promise);
  return promise;
}

function getMentionContext(text: string, cursor: number): MentionContext | null {
  if (cursor < 0 || cursor > text.length) return null;

  let segmentStart = cursor;
  while (segmentStart > 0 && !/\s/.test(text[segmentStart - 1])) {
    segmentStart -= 1;
  }

  const segment = text.slice(segmentStart, cursor);
  const atOffset = segment.lastIndexOf('@');
  if (atOffset < 0) return null;

  const atIndex = segmentStart + atOffset;
  const beforeAt = text[atIndex - 1];
  if (beforeAt && /[A-Za-z0-9_.-]/.test(beforeAt)) {
    return null; // Ignore email-like tokens.
  }

  const query = text.slice(atIndex + 1, cursor);
  if (/\s/.test(query)) return null;

  return {
    start: atIndex,
    cursor,
    query,
  };
}

function fuzzySubsequenceScore(target: string, query: string): number {
  if (!query) return 0;
  let score = 0;
  let targetIndex = 0;
  let lastMatch = -1;

  for (const char of query) {
    const matchIndex = target.indexOf(char, targetIndex);
    if (matchIndex < 0) return -1;
    score += matchIndex === lastMatch + 1 ? 8 : 2;
    score -= Math.floor(matchIndex / 12);
    lastMatch = matchIndex;
    targetIndex = matchIndex + 1;
  }

  return score;
}

function scoreIndexedFile(file: IndexedProjectFile, queryRaw: string): number {
  const query = queryRaw.trim().toLowerCase();
  if (!query) return 2_000 - file.relativePath.length;
  if (file.nameLower === query) return 10_000;
  if (file.relativePathLower === query) return 9_500;
  if (file.nameLower.startsWith(query)) return 8_500 - file.nameLower.length;
  if (file.relativePathLower.startsWith(query)) return 8_000 - file.relativePath.length;

  const nameIndex = file.nameLower.indexOf(query);
  if (nameIndex >= 0) return 7_000 - (nameIndex * 20);

  const pathIndex = file.relativePathLower.indexOf(query);
  if (pathIndex >= 0) return 6_500 - (pathIndex * 8);

  const fuzzyNameScore = fuzzySubsequenceScore(file.nameLower, query);
  const fuzzyPathScore = fuzzySubsequenceScore(file.relativePathLower, query);
  const fuzzyScore = Math.max(fuzzyNameScore, fuzzyPathScore >= 0 ? fuzzyPathScore - 2 : -1);
  if (fuzzyScore >= 0) return 5_000 + fuzzyScore;

  return -1;
}

function getRankedFiles(files: IndexedProjectFile[], query: string, limit: number): IndexedProjectFile[] {
  return files
    .map((file) => ({ file, score: scoreIndexedFile(file, query) }))
    .filter((entry) => entry.score >= 0)
    .sort((a, b) => (
      b.score - a.score
      || a.file.relativePath.length - b.file.relativePath.length
      || a.file.relativePathLower.localeCompare(b.file.relativePathLower)
    ))
    .slice(0, limit)
    .map((entry) => entry.file);
}

function parseContentEditableToSegments(container: HTMLDivElement): Segment[] {
  const segments: Segment[] = [];
  const walk = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const v = node.textContent ?? '';
      if (v) segments.push({ type: 'text', value: v });
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const el = node as HTMLElement;
    if (el.getAttribute?.('data-chip-path')) {
      segments.push({ type: 'chip', path: el.getAttribute('data-chip-path') ?? '' });
      return;
    }
    for (let i = 0; i < node.childNodes.length; i++) {
      walk(node.childNodes[i]!);
    }
  };
  walk(container);
  if (segments.length === 0) return [{ type: 'text', value: '' }];
  return segments;
}

function getContentEditableTextAndCursor(container: HTMLDivElement): { text: string; cursor: number } {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return { text: container.innerText ?? '', cursor: 0 };
  const text = container.innerText ?? '';
  const range = sel.getRangeAt(0);
  const pre = document.createRange();
  pre.setStart(container, 0);
  pre.setEnd(range.startContainer, range.startOffset);
  const cursor = (pre.toString().length ?? 0);
  return { text, cursor };
}

function setRangeByOffset(container: Node, range: Range, startOffset: number, endOffset: number): boolean {
  let pos = 0;
  let startRes: { node: Node; offset: number } | null = null;
  let endRes: { node: Node; offset: number } | null = null;

  const walk = (node: Node): boolean => {
    if (node.nodeType === Node.TEXT_NODE) {
      const len = (node.textContent ?? '').length;
      if (startRes == null && pos + len >= startOffset) {
        startRes = { node, offset: startOffset - pos };
      }
      if (endRes == null && pos + len >= endOffset) {
        endRes = { node, offset: endOffset - pos };
      }
      pos += len;
      return startRes != null && endRes != null;
    }
    if (node.nodeType === Node.ELEMENT_NODE) {
      const el = node as HTMLElement;
      if (el.getAttribute?.('data-chip-path')) {
        const label = fileLabel(el.getAttribute('data-chip-path') ?? '');
        if (startRes == null && pos + label.length >= startOffset) {
          startRes = { node: el, offset: 0 };
        }
        if (endRes == null && pos + label.length >= endOffset) {
          endRes = { node: el, offset: el.childNodes.length };
        }
        pos += label.length;
        return startRes != null && endRes != null;
      }
    }
    for (let i = 0; i < node.childNodes.length; i++) {
      if (walk(node.childNodes[i]!)) return true;
    }
    return false;
  };

  walk(container);
  if (startRes && endRes) {
    range.setStart(startRes.node, startRes.offset);
    range.setEnd(endRes.node, endRes.offset);
    return true;
  }
  return false;
}

function fileToBase64(file: File): Promise<{ data: string; mimeType: string; name: string }> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.includes(',') ? result.split(',')[1]! : result;
      resolve({ data: base64, mimeType: file.type || 'image/png', name: file.name });
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export function MessageInput({
  value,
  onChange,
  referencedFiles = [],
  onReferencedFilesChange,
  attachments = [],
  onAttachmentsChange,
  onSubmit,
  onCancel,
  composeMode = 'default',
  onComposeModeChange,
  activeChatId,
  activeProjectPath = null,
  disabled = false,
  isProcessing = false,
}: MessageInputProps) {
  const editRef = useRef<HTMLDivElement>(null);
  const [mentionContext, setMentionContext] = useState<MentionContext | null>(null);
  const [segments, setSegments] = useState<Segment[]>(() => valueAndRefsToSegments(value, referencedFiles));
  const lastEmittedRef = useRef<{ value: string; refs: string[] } | null>(null);

  const setEditContentFromSegments = useCallback((nextSegments: Segment[]) => {
    const el = editRef.current;
    if (!el) return;
    el.replaceChildren();
    for (const s of nextSegments) {
      if (s.type === 'text') {
        if (s.value || nextSegments.length > 1) {
          el.appendChild(document.createTextNode(s.value));
        }
      } else {
        const span = document.createElement('span');
        span.setAttribute('data-chip-path', s.path);
        span.contentEditable = 'false';
        span.className = 'inline-flex items-center gap-1 px-2 py-0.5 rounded-md border border-aqua-500/30 bg-aqua-500/10 text-[11px] text-aqua-200 max-w-full mx-0.5 align-middle';
        span.style.display = 'inline-flex';
        const label = fileLabel(s.path);
        span.innerHTML = `<span class="truncate max-w-[180px]">${label}</span><button type="button" data-remove-chip="${s.path.replace(/"/g, '&quot;')}" class="text-aqua-100/80 hover:text-aqua-100 ml-1" title="Remove"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg></button>`;
        el.appendChild(span);
      }
    }
  }, []);

  useEffect(() => {
    const prev = lastEmittedRef.current;
    const isReset = value === '' && referencedFiles.length === 0;
    const isNew = prev == null || value !== prev.value || referencedFiles.length !== prev.refs.length || referencedFiles.some((r, i) => r !== prev.refs[i]);

    if (isReset || isNew) {
      const next = isReset ? [{ type: 'text' as const, value: '' }] : valueAndRefsToSegments(value, referencedFiles);
      setSegments(next);
      lastEmittedRef.current = { value: isReset ? '' : segmentsToValue(next), refs: isReset ? [] : segmentsToRefs(next) };
      setEditContentFromSegments(next);
    }
  }, [value, referencedFiles, setEditContentFromSegments]);

  const [fileIndex, setFileIndex] = useState<IndexedProjectFile[] | null>(null);
  const [indexLoading, setIndexLoading] = useState(false);
  const [indexError, setIndexError] = useState<string | null>(null);
  const [selectedMentionIndex, setSelectedMentionIndex] = useState(0);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!onAttachmentsChange || !activeChatId || disabled) return;
      const files = Array.from(e.dataTransfer?.files ?? []);
      const imageFiles = files.filter(
        (f) => IMAGE_MIMES.has(f.type) && f.size <= MAX_ATTACHMENT_SIZE_MB * 1024 * 1024,
      );
      if (imageFiles.length === 0) return;
      Promise.all(imageFiles.map(fileToBase64)).then((newAtts) => {
        onAttachmentsChange([...attachments, ...newAtts]);
      });
    },
    [onAttachmentsChange, attachments, activeChatId, disabled],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  }, []);

  const removeAttachment = useCallback(
    (index: number) => {
      if (!onAttachmentsChange) return;
      onAttachmentsChange(attachments.filter((_, i) => i !== index));
    },
    [onAttachmentsChange, attachments],
  );

  const handlePaste = useCallback(
    (e: React.ClipboardEvent) => {
      if (!onAttachmentsChange || !activeChatId || disabled) return;
      const items = e.clipboardData?.items;
      if (!items) return;
      const imageFiles: File[] = [];
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item?.kind === 'file' && IMAGE_MIMES.has(item.type)) {
          const file = item.getAsFile();
          if (file && file.size <= MAX_ATTACHMENT_SIZE_MB * 1024 * 1024) {
            imageFiles.push(file);
          }
        }
      }
      if (imageFiles.length > 0) {
        e.preventDefault();
        Promise.all(imageFiles.map(fileToBase64)).then((newAtts) => {
          onAttachmentsChange([...attachments, ...newAtts]);
        });
      }
    },
    [onAttachmentsChange, attachments, activeChatId, disabled],
  );

  const mentionOpen = mentionContext != null;

  useEffect(() => {
    setMentionContext(null);
    setSelectedMentionIndex(0);
    setIndexError(null);
    setIndexLoading(false);
    if (!activeProjectPath) {
      setFileIndex(null);
      return;
    }
    setFileIndex(fileIndexCache.get(activeProjectPath) ?? null);
  }, [activeProjectPath]);

  useEffect(() => {
    if (!mentionOpen || !activeProjectPath) {
      setIndexLoading(false);
      return;
    }
    if (fileIndexCache.has(activeProjectPath)) {
      setFileIndex(fileIndexCache.get(activeProjectPath) ?? null);
      setIndexLoading(false);
      return;
    }

    let cancelled = false;
    setIndexLoading(true);
    setIndexError(null);

    getProjectFileIndex(activeProjectPath)
      .then((indexedFiles) => {
        if (cancelled) return;
        setFileIndex(indexedFiles);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : 'Failed to index project files.';
        setIndexError(message);
      })
      .finally(() => {
        if (!cancelled) setIndexLoading(false);
      });

    return () => {
      cancelled = true;
      setIndexLoading(false);
    };
  }, [mentionOpen, activeProjectPath]);

  const mentionSuggestions = useMemo(() => {
    if (!mentionContext || !fileIndex) return [];
    return getRankedFiles(fileIndex, mentionContext.query, MAX_VISIBLE_MENTIONS);
  }, [mentionContext, fileIndex]);

  useEffect(() => {
    setSelectedMentionIndex(0);
  }, [mentionContext?.query, mentionContext?.start]);

  useEffect(() => {
    if (selectedMentionIndex <= mentionSuggestions.length - 1) return;
    setSelectedMentionIndex(Math.max(mentionSuggestions.length - 1, 0));
  }, [mentionSuggestions.length, selectedMentionIndex]);

  const setMentionFromCursor = (text: string, cursor: number | null) => {
    if (cursor == null) {
      setMentionContext(null);
      return;
    }
    setMentionContext(getMentionContext(text, cursor));
  };

  const syncFromDom = useCallback(() => {
    const el = editRef.current;
    if (!el) return;
    const nextSegments = parseContentEditableToSegments(el);
    const text = segmentsToValue(nextSegments);
    const refs = segmentsToRefs(nextSegments);
    lastEmittedRef.current = { value: text, refs };
    setSegments(nextSegments);
    onChange(text);
    onReferencedFilesChange?.(refs);
  }, [onChange, onReferencedFilesChange]);

  const removeReferencedFile = (path: string) => {
    const el = editRef.current;
    if (!el) return;
    const chip = Array.from(el.querySelectorAll('[data-chip-path]')).find((n) => (n as HTMLElement).dataset.chipPath === path);
    chip?.remove();
    syncFromDom();
  };

  const insertMention = (file: IndexedProjectFile) => {
    if (!mentionContext) return;
    const el = editRef.current;
    if (!el) return;
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    const range = sel.getRangeAt(0);
    setRangeByOffset(el, range, mentionContext.start, mentionContext.cursor);

    const span = document.createElement('span');
    span.setAttribute('data-chip-path', file.path);
    span.contentEditable = 'false';
    span.className = 'inline-flex items-center gap-1 px-2 py-0.5 rounded-md border border-aqua-500/30 bg-aqua-500/10 text-[11px] text-aqua-200 max-w-full mx-0.5 align-middle';
    span.style.display = 'inline-flex';
    const label = fileLabel(file.path);
    span.innerHTML = `<span class="truncate max-w-[180px]">${label}</span><button type="button" data-remove-chip="${file.path.replace(/"/g, '&quot;')}" class="text-aqua-100/80 hover:text-aqua-100 ml-1" title="Remove"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg></button>`;

    range.deleteContents();
    range.insertNode(span);
    range.collapse(false);
    sel.removeAllRanges();
    sel.addRange(range);
    el.focus();

    setMentionContext(null);
    setSelectedMentionIndex(0);
    syncFromDom();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (mentionContext && mentionSuggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedMentionIndex((prev) => (prev + 1) % mentionSuggestions.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedMentionIndex((prev) => (prev - 1 + mentionSuggestions.length) % mentionSuggestions.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        insertMention(mentionSuggestions[selectedMentionIndex] ?? mentionSuggestions[0]);
        return;
      }
    }

    if (mentionContext && e.key === 'Escape') {
      e.preventDefault();
      setMentionContext(null);
      return;
    }

    if (e.key === 'Backspace' && !mentionContext && referencedFiles.length > 0) {
      const el = editRef.current;
      if (el) {
        const { text, cursor } = getContentEditableTextAndCursor(el);
        if (cursor === 0 && !text.trim()) {
          e.preventDefault();
          removeReferencedFile(referencedFiles[referencedFiles.length - 1]!);
          return;
        }
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (isProcessing) onCancel?.();
      else onSubmit();
    }
  };

  const showMentionPopup = Boolean(mentionContext && activeProjectPath);

  return (
    <div className={cn('space-y-2', !activeChatId && 'opacity-50 pointer-events-none')}>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => onComposeModeChange?.('default')}
          className={cn(
            'px-2 py-1 text-[10px] rounded-md border transition-colors',
            composeMode === 'default'
              ? 'bg-gray-700 border-gray-500 text-gray-100'
              : 'border-gray-700/60 text-gray-400 hover:text-gray-200 hover:bg-gray-800/70',
          )}
        >
          Chat
        </button>
        <button
          type="button"
          onClick={() => onComposeModeChange?.('planning')}
          className={cn(
            'px-2 py-1 text-[10px] rounded-md border transition-colors',
            composeMode === 'planning'
              ? 'bg-cyan-500/20 border-cyan-400/50 text-cyan-200'
              : 'border-gray-700/60 text-gray-400 hover:text-cyan-200 hover:bg-cyan-500/10',
          )}
        >
          Planning
        </button>
      </div>
      <div className="flex items-end gap-2">
        <div
          className="flex-1 relative"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {attachments.map((att, i) => (
                <div
                  key={i}
                  className="relative group inline-flex rounded-lg border border-gray-600 overflow-hidden bg-gray-800/80"
                >
                  <img
                    src={`data:${att.mimeType};base64,${att.data}`}
                    alt={att.name ?? 'Attachment'}
                    className="w-14 h-14 object-cover"
                  />
                  <button
                    type="button"
                    onClick={() => removeAttachment(i)}
                    className="absolute top-0.5 right-0.5 p-1 rounded bg-black/60 text-gray-300 hover:text-white hover:bg-red-600/80 transition-colors"
                    title="Remove"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
          {showMentionPopup && (
            <div className="absolute bottom-full left-0 right-0 mb-2 z-20 rounded-xl border border-gray-700/70 bg-gray-850 shadow-xl shadow-black/40 overflow-hidden">
              <div className="px-3 py-1.5 text-[10px] uppercase tracking-wide text-gray-400 border-b border-gray-700/60">
                Project Files
              </div>
              <div className="max-h-56 overflow-y-auto">
                {indexLoading && (
                  <div className="px-3 py-3 text-xs text-gray-400">Indexing files in this project...</div>
                )}
                {!indexLoading && indexError && (
                  <div className="px-3 py-3 text-xs text-red-300 break-words">{indexError}</div>
                )}
                {!indexLoading && !indexError && mentionSuggestions.length === 0 && (
                  <div className="px-3 py-3 text-xs text-gray-400">No matching files</div>
                )}
                {!indexLoading && !indexError && mentionSuggestions.map((file, index) => (
                  <button
                    key={file.path}
                    type="button"
                    onMouseEnter={() => setSelectedMentionIndex(index)}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      insertMention(file);
                    }}
                    className={cn(
                      'w-full text-left px-3 py-2.5 border-b border-gray-800/70 last:border-b-0 transition-colors',
                      index === selectedMentionIndex
                        ? 'bg-aqua-500/15 text-gray-100'
                        : 'hover:bg-gray-800/80 text-gray-200',
                    )}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="w-3.5 h-3.5 shrink-0 text-aqua-400/80" />
                      <span className="truncate text-xs">{file.name}</span>
                    </div>
                    <div className="mt-1 pl-5 text-[11px] text-gray-500 font-mono truncate">{file.relativePath}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="w-full bg-gray-800 border border-gray-700/50 rounded-xl text-sm transition-colors focus-within:border-aqua-500/40 focus-within:shadow-[0_0_0_2px_rgba(34,211,216,0.4),0_0_0_3px_#16161f,0_0_0_4px_rgba(34,211,216,0.12)]">
            <div
              ref={editRef}
              contentEditable={!!activeChatId && !disabled}
              suppressContentEditableWarning
              role="textbox"
              aria-multiline="true"
              data-placeholder={
                !activeChatId
                  ? 'Select or create a chat to continue'
                  : composeMode === 'planning'
                    ? 'Describe what to explore, plan, or refine in the active plan...'
                    : 'Describe what you want to build...'
              }
              className="min-h-[40px] max-h-[200px] overflow-y-auto rounded-xl px-3 py-2 text-gray-200 text-sm focus:outline-none focus:ring-0 focus-visible:shadow-none empty:before:content-[attr(data-placeholder)] empty:before:text-gray-500"
              onInput={() => {
                syncFromDom();
                const el = editRef.current;
                if (el) {
                  const { text, cursor } = getContentEditableTextAndCursor(el);
                  setMentionFromCursor(text, cursor);
                }
              }}
              onSelect={() => {
                const el = editRef.current;
                if (el) {
                  const { text, cursor } = getContentEditableTextAndCursor(el);
                  setMentionFromCursor(text, cursor);
                }
              }}
              onMouseDown={(e) => {
                const target = (e.target as HTMLElement).closest('button[data-remove-chip]');
                if (target) {
                  e.preventDefault();
                  const path = target.getAttribute('data-remove-chip');
                  if (path) removeReferencedFile(path);
                }
              }}
              onKeyDown={(e) => handleKeyDown(e)}
              onPaste={handlePaste}
            />
          </div>
        </div>
        {isProcessing ? (
          <button
            onClick={onCancel}
            disabled={!activeChatId}
            className="p-3 bg-amber-500/90 hover:bg-amber-500 text-gray-950 rounded-xl transition-colors shadow-lg shadow-amber-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Stop"
          >
            <Square className="w-4 h-4 fill-current" />
          </button>
        ) : (
          <button
            onClick={onSubmit}
            disabled={!activeChatId || disabled}
            className="p-3 bg-aqua-500 hover:bg-aqua-400 text-gray-950 rounded-xl transition-colors shadow-lg shadow-aqua-500/20 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-aqua-500"
          >
            <Send className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}
