/**
 * React hooks that wrap the ApiClient for use in components.
 * Re-exports from individual hook modules.
 */

export { useChatHistory } from './hooks/useChatHistory';
export { useProjects } from './hooks/useProjects';
export { useFilesystemBrowser } from './hooks/useFilesystemBrowser';
export { useSettings } from './hooks/useSettings';
export { useOpenRouter } from './hooks/useOpenRouter';
export { useGroq } from './hooks/useGroq';
export { useOpenAISub } from './hooks/useOpenAISub';
export { useMcp } from './hooks/useMcp';
export { useAgentEvents } from './hooks/useAgentEvents';

export { api as defaultApiClient } from './client';
export type { ApiClient } from './client';
