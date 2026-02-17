import { useEffect, useRef } from 'react';
import { Loader2, X } from 'lucide-react';
import { cn } from '../utils/cn';

export interface ModalProps {
  /** Whether the modal is visible. When false, modal is hidden but stays mounted for instant reopen. */
  visible: boolean;
  /** Called when user clicks backdrop, presses Escape, or closes via header button. */
  onClose: () => void;
  /** Optional loading state — shows spinner overlay when true. */
  loading?: boolean;
  /** Custom loading label when loading. Default "Loading...". */
  loadingLabel?: string;
  /** Optional title for the modal header. */
  title?: string;
  /** Optional subtitle/description. */
  subtitle?: string;
  /** Optional icon element (e.g. for header). */
  icon?: React.ReactNode;
  /** Optional footer content. */
  footer?: React.ReactNode;
  /** Panel max width. Default 'max-w-3xl'. */
  maxWidth?: 'max-w-sm' | 'max-w-md' | 'max-w-lg' | 'max-w-xl' | 'max-w-2xl' | 'max-w-3xl';
  /** Panel max height. Default 'max-h-[80vh]'. */
  maxHeight?: string;
  /** Content to render. Use children for custom content, or use title/subtitle/icon/footer for standard layout. */
  children: React.ReactNode;
  /** Optional class for the panel. */
  panelClassName?: string;
}

/**
 * Shared modal overlay with animation, click-outside-to-close, and Escape handling.
 * Stays mounted with visibility toggled for instant open.
 */
export function Modal({
  visible,
  onClose,
  loading = false,
  loadingLabel = 'Loading...',
  title,
  subtitle,
  icon,
  footer,
  maxWidth = 'max-w-3xl',
  maxHeight = 'max-h-[80vh]',
  children,
  panelClassName,
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Escape key
  useEffect(() => {
    if (!visible) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [visible, onClose]);

  // Click outside (backdrop)
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div
      className={cn(
        'fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm transition-opacity duration-200',
        visible ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none invisible',
      )}
      aria-hidden={!visible}
      aria-modal={visible}
    >
      <div
        className={cn(
          'flex w-full justify-center mx-4 transition-all duration-200',
          visible ? 'opacity-100 scale-100' : 'opacity-0 scale-95',
        )}
        onClick={handleBackdropClick}
        role="presentation"
      >
        <div
          ref={panelRef}
          className={cn(
            'relative w-full bg-[#1a1a24] border border-gray-700/50 rounded-lg shadow-2xl flex flex-col',
            maxWidth,
            maxHeight || undefined,
            panelClassName,
          )}
          onClick={(e) => e.stopPropagation()}
          role="dialog"
          aria-modal="true"
          aria-labelledby={title ? 'modal-title' : undefined}
        >
          {(title || icon) && (
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700/50 shrink-0">
              <div className="flex items-center gap-3">
                {icon && (
                  <div className="p-2 bg-cyan-500/10 rounded-lg border border-cyan-500/20">
                    {icon}
                  </div>
                )}
                {(title || subtitle) && (
                  <div>
                    {title && (
                      <h2 id="modal-title" className="text-lg font-semibold text-gray-100">
                        {title}
                      </h2>
                    )}
                    {subtitle && <p className="text-xs text-gray-400">{subtitle}</p>}
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={onClose}
                className="p-2 text-gray-400 hover:text-gray-200 hover:bg-gray-700/50 rounded-lg transition-colors"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          )}

          <div className="flex-1 overflow-y-auto relative min-h-0">
            {loading ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center py-12 text-gray-400">
                <Loader2 className="w-8 h-8 animate-spin mb-3" />
                <p className="text-sm">{loadingLabel}</p>
              </div>
            ) : null}
            <div className={cn(loading && 'invisible')}>{children}</div>
          </div>

          {footer ? (
            <div className="px-6 py-4 border-t border-gray-700/50 bg-gray-800/20 shrink-0">
              {footer}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
