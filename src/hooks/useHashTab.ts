import { useState, useEffect, useCallback } from 'react';

/**
 * Syncs activeTab to window.location.hash for deep-linking without adding react-router.
 * @param defaultTab - The default tab when hash is empty or invalid.
 * @param validTabs - Valid tab values to match against hash.
 */
export function useHashTab<T extends string>(
  defaultTab: T,
  validTabs: readonly T[] = [defaultTab] as unknown as readonly T[],
): [T, (tab: T) => void] {
  const parseHash = useCallback((): T => {
    const hash = (globalThis as Window & typeof globalThis).location.hash.slice(1);
    if (validTabs.includes(hash as T)) return hash as T;
    return defaultTab;
  }, [defaultTab, validTabs]);

  const [activeTab, setActiveTab] = useState<T>(parseHash);

  useEffect(() => {
    const handleHashChange = () => setActiveTab(parseHash());
    globalThis.addEventListener('hashchange', handleHashChange);
    return () => globalThis.removeEventListener('hashchange', handleHashChange);
  }, [parseHash]);

  const setActiveTabWithHash = useCallback(
    (tab: T) => {
      (globalThis as Window & typeof globalThis).location.hash = tab;
      setActiveTab(tab);
    },
    [],
  );

  return [activeTab, setActiveTabWithHash];
}
