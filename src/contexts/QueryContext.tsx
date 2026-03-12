import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle, Pencil } from 'lucide-react';
import { Modal } from '@/components/Modal';
import { cn } from '@/utils/cn';

export interface QueryContextValue {
  /** Show a confirm dialog. Returns true if user confirms, false if cancelled. */
  confirm: (message: string, options?: ConfirmOptions) => Promise<boolean>;
  /** Show a prompt dialog. Returns the trimmed string if user confirms, null if cancelled. */
  prompt: (message: string, defaultValue?: string) => Promise<string | null>;
}

export interface ConfirmOptions {
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'danger';
}

interface ConfirmState {
  message: string;
  options?: ConfirmOptions;
  resolve: (value: boolean) => void;
}

interface PromptState {
  message: string;
  defaultValue: string;
  resolve: (value: string | null) => void;
}

const QueryContext = createContext<QueryContextValue | null>(null);

export function useQuery(): QueryContextValue {
  const ctx = useContext(QueryContext);
  if (!ctx) throw new Error('useQuery must be used within QueryProvider');
  return ctx;
}

interface QueryProviderProps {
  readonly children: ReactNode;
}

export function QueryProvider({ children }: QueryProviderProps) {
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null);
  const [promptState, setPromptState] = useState<PromptState | null>(null);

  const confirmFn = useCallback((message: string, options?: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      setConfirmState({ message, options, resolve });
    });
  }, []);

  const promptFn = useCallback((message: string, defaultValue = '') => {
    return new Promise<string | null>((resolve) => {
      setPromptState({ message, defaultValue, resolve });
    });
  }, []);

  const value = useMemo(
    () => ({ confirm: confirmFn, prompt: promptFn }),
    [confirmFn, promptFn],
  );

  const handleConfirmOk = () => {
    if (confirmState) {
      confirmState.resolve(true);
      setConfirmState(null);
    }
  };

  const handleConfirmCancel = () => {
    if (confirmState) {
      confirmState.resolve(false);
      setConfirmState(null);
    }
  };

  const handlePromptOk = (value: string) => {
    if (promptState) {
      const trimmed = value.trim();
      promptState.resolve(trimmed || null);
      setPromptState(null);
    }
  };

  const handlePromptCancel = () => {
    if (promptState) {
      promptState.resolve(null);
      setPromptState(null);
    }
  };

  return (
    <QueryContext.Provider value={value}>
      {children}
      {confirmState &&
        createPortal(
          <ConfirmModal
            message={confirmState.message}
            options={confirmState.options}
            onConfirm={handleConfirmOk}
            onCancel={handleConfirmCancel}
          />,
          document.body,
        )}
      {promptState &&
        createPortal(
          <PromptModal
            message={promptState.message}
            defaultValue={promptState.defaultValue}
            onConfirm={handlePromptOk}
            onCancel={handlePromptCancel}
          />,
          document.body,
        )}
    </QueryContext.Provider>
  );
}

interface ConfirmModalProps {
  readonly message: string;
  readonly options?: ConfirmOptions;
  readonly onConfirm: () => void;
  readonly onCancel: () => void;
}

function ConfirmModal({
  message,
  options = {},
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const {
    confirmLabel = 'OK',
    cancelLabel = 'Cancel',
    variant = 'default',
  } = options;
  const isDanger = variant === 'danger';

  return (
    <Modal visible onClose={onCancel} maxWidth="max-w-sm" overlayClassName="z-[9999]">
      <div className="px-6 py-4 flex flex-col gap-4">
        <div className="flex items-start gap-3">
          <div
            className={cn(
              'shrink-0 p-2 rounded-lg border',
              isDanger
                ? 'bg-red-500/10 border-red-500/20'
                : 'bg-aqua-500/10 border-aqua-500/20',
            )}
          >
            <AlertTriangle
              className={cn(
                'w-5 h-5',
                isDanger ? 'text-red-400' : 'text-aqua-400',
              )}
            />
          </div>
          <p className="text-gray-200 text-sm leading-relaxed pt-0.5">{message}</p>
        </div>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-700/60 rounded-lg transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={cn(
              'px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors',
              isDanger
                ? 'bg-red-600 hover:bg-red-500'
                : 'bg-aqua-600 hover:bg-aqua-500',
            )}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  );
}

interface PromptModalProps {
  readonly message: string;
  readonly defaultValue: string;
  readonly onConfirm: (value: string) => void;
  readonly onCancel: () => void;
}

function PromptModal({
  message,
  defaultValue,
  onConfirm,
  onCancel,
}: PromptModalProps) {
  const [value, setValue] = useState(defaultValue);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onConfirm(value);
  };

  return (
    <Modal visible onClose={onCancel} maxWidth="max-w-sm" overlayClassName="z-[9999]">
      <form onSubmit={handleSubmit} className="px-6 py-4 flex flex-col gap-4">
        <div className="flex items-start gap-3">
          <div className="shrink-0 p-2 rounded-lg border bg-aqua-500/10 border-aqua-500/20">
            <Pencil className="w-5 h-5 text-aqua-400" />
          </div>
          <div className="flex-1 min-w-0">
            <label className="block text-gray-200 text-sm mb-2">{message}</label>
            <input
              ref={inputRef}
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-gray-800 border border-gray-600 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-aqua-500/50 focus:border-aqua-500/50"
              autoFocus
              autoComplete="off"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-700/60 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="px-4 py-2 text-sm font-medium text-white bg-aqua-600 hover:bg-aqua-500 rounded-lg transition-colors"
          >
            OK
          </button>
        </div>
      </form>
    </Modal>
  );
}
