import { useState, useEffect, useCallback } from 'react';
import { api as defaultApi, ApiClient } from '@/api/client';
import { useAsyncState } from '@/api/normalizers';
import type { GetFsChildrenResponse } from '@/api/types';

export function useFilesystemBrowser(initialPath?: string, client: ApiClient = defaultApi) {
  const [state, run] = useAsyncState<GetFsChildrenResponse>();
  const [path, setPath] = useState(initialPath ?? '');
  const [allowedRoots, setAllowedRoots] = useState<string[]>([]);

  const load = useCallback(
    async (nextPath?: string) => {
      const target = nextPath ?? path;
      const res = await run(client.getFsChildren(target || undefined));
      if (res.ok) {
        setPath(res.data.path);
        setAllowedRoots(res.data.allowedRoots);
      }
      return res;
    },
    [client, path, run],
  );

  useEffect(() => {
    load(initialPath);
  }, [initialPath, load]);

  return {
    data: state.data,
    loading: state.loading,
    error: state.error,
    path,
    allowedRoots,
    load,
    setPath,
  };
}
