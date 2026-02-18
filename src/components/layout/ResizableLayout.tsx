import { useCallback, useRef, useEffect } from 'react';

interface ResizableLayoutProps {
  chatWidth: number;
  onChatWidthChange: (width: number) => void;
  leftPanel: React.ReactNode;
  rightPanel: React.ReactNode;
}

export function ResizableLayout({
  chatWidth,
  onChatWidthChange,
  leftPanel,
  rightPanel,
}: ResizableLayoutProps) {
  const isDragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const pct = (x / rect.width) * 100;
      onChatWidthChange(Math.min(Math.max(pct, 25), 75));
    },
    [onChatWidthChange],
  );

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

  return (
    <div ref={containerRef} className="flex-1 flex gap-0 p-3 overflow-hidden">
      <div className="flex flex-col overflow-hidden" style={{ width: `${chatWidth}%` }}>
        {leftPanel}
      </div>
      <div
        className="resize-handle group flex items-center justify-center w-3 flex-shrink-0 cursor-col-resize z-10"
        onMouseDown={handleMouseDown}
      >
        <div className="w-[3px] h-12 rounded-full bg-gray-700/50 group-hover:bg-aqua-400/50 group-active:bg-aqua-400/80 transition-colors" />
      </div>
      <div className="overflow-hidden" style={{ width: `${100 - chatWidth}%` }}>
        {rightPanel}
      </div>
    </div>
  );
}
