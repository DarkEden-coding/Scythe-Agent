import { useRef, useEffect, useCallback } from 'react';

const BOTTOM_THRESHOLD_PX = 80;

function isAtBottom(el: HTMLElement): boolean {
  const { scrollTop, scrollHeight, clientHeight } = el;
  return scrollTop + clientHeight >= scrollHeight - BOTTOM_THRESHOLD_PX;
}

/**
 * Auto-scrolls a scroll container to the bottom when content changes,
 * but only if the user is already at/near the bottom (hasn't scrolled up).
 */
export function useAutoScroll<T>(
  scrollTrigger: T,
  options?: { enabled?: boolean },
) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const shouldAutoScrollRef = useRef(true);

  const onScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    shouldAutoScrollRef.current = isAtBottom(el);
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || options?.enabled === false) return;
    if (!shouldAutoScrollRef.current) return;
    el.scrollTop = el.scrollHeight - el.clientHeight;
  }, [scrollTrigger, options?.enabled]);

  return { ref: containerRef, onScroll };
}
