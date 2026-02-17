import { useState, useEffect, useCallback } from 'react';
import { api as defaultApi, ApiClient } from '@/api/client';
import { useAsyncState, toDate } from '@/api/normalizers';
import type { GetProjectsResponse } from '@/api/types';

export function useProjects(client: ApiClient = defaultApi) {
  const [state, run] = useAsyncState<GetProjectsResponse>({ projects: [] });
  const [projects, setProjects] = useState<GetProjectsResponse['projects']>([]);

  useEffect(() => {
    run(client.getProjects()).then((res) => {
      if (res.ok) {
        setProjects(res.data.projects);
      }
    });
  }, [client, run]);

  const normalizedProjects = (projects ?? []).map((project) => ({
    ...project,
    lastAccessed: toDate(project.lastAccessed),
    chats: project.chats.map((chat) => ({
      ...chat,
      timestamp: toDate(chat.timestamp),
    })),
  }));

  const refresh = useCallback(async () => {
    const res = await run(client.getProjects());
    if (res.ok) {
      setProjects(res.data.projects);
    }
    return res;
  }, [client, run]);

  const createProject = useCallback(
    async (name: string, path: string) => {
      const res = await client.createProject({ name, path });
      if (res.ok) {
        await refresh();
      }
      return res;
    },
    [client, refresh],
  );

  const createChat = useCallback(
    async (projectId: string, title?: string) => {
      const res = await client.createChat({ projectId, title: title?.trim() || undefined });
      if (res.ok) {
        await refresh();
      }
      return res;
    },
    [client, refresh],
  );

  const renameProject = useCallback(
    async (projectId: string, name: string) => {
      const res = await client.updateProject(projectId, { name });
      if (res.ok) {
        await refresh();
      }
      return res;
    },
    [client, refresh],
  );

  const renameChat = useCallback(
    async (chatId: string, title: string) => {
      const res = await client.updateChat({ chatId, title });
      if (res.ok) {
        await refresh();
      }
      return res;
    },
    [client, refresh],
  );

  const pinChat = useCallback(
    async (chatId: string, isPinned: boolean) => {
      const res = await client.updateChat({ chatId, isPinned });
      if (res.ok) {
        await refresh();
      }
      return res;
    },
    [client, refresh],
  );

  const deleteProject = useCallback(
    async (projectId: string) => {
      const res = await client.deleteProject(projectId);
      if (res.ok) {
        await refresh();
      }
      return res;
    },
    [client, refresh],
  );

  const deleteChat = useCallback(
    async (chatId: string) => {
      const res = await client.deleteChat({ chatId });
      if (res.ok) {
        await refresh();
      }
      return res;
    },
    [client, refresh],
  );

  const reorderProjects = useCallback(
    async (projectIds: string[]) => {
      const res = await client.reorderProjects({ projectIds });
      if (res.ok) {
        setProjects(res.data.projects);
      }
      return res;
    },
    [client],
  );

  const reorderChats = useCallback(
    async (projectId: string, chatIds: string[]) => {
      const res = await client.reorderChats({ projectId, chatIds });
      if (res.ok) {
        setProjects(res.data.projects);
      }
      return res;
    },
    [client],
  );

  return {
    projects: normalizedProjects,
    loading: state.loading,
    error: state.error,
    refresh,
    createProject,
    createChat,
    renameProject,
    renameChat,
    pinChat,
    deleteProject,
    deleteChat,
    reorderProjects,
    reorderChats,
  };
}
