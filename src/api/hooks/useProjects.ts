import { useState, useEffect, useCallback } from 'react';
import { api as defaultApi, ApiClient } from '@/api/client';
import { useAsyncState, toDate } from '@/api/normalizers';
import type {
  GetProjectsResponse,
  GetProjectMemoriesResponse,
  UpsertProjectMemoryRequest,
} from '@/api/types';

export function useProjects(client: ApiClient = defaultApi) {
  const [state, run] = useAsyncState<GetProjectsResponse>({ projects: [] });
  const [projects, setProjects] = useState<GetProjectsResponse['projects']>([]);
  const [memoriesByProject, setMemoriesByProject] = useState<Record<string, GetProjectMemoriesResponse['memories']>>({});

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

  const getProjectMemories = useCallback(
    async (projectId: string, options?: { force?: boolean }) => {
      if (!options?.force && memoriesByProject[projectId]) {
        return { ok: true as const, data: { memories: memoriesByProject[projectId] }, timestamp: new Date().toISOString() };
      }
      const res = await client.getProjectMemories(projectId);
      if (res.ok) {
        setMemoriesByProject((prev) => ({
          ...prev,
          [projectId]: res.data.memories,
        }));
      }
      return res;
    },
    [client, memoriesByProject],
  );

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
        setProjects((prev) =>
          prev.map((p) => ({ ...p, chats: p.chats.filter((c) => c.id !== chatId) })),
        );
      }
      return res;
    },
    [client],
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

  const upsertProjectMemory = useCallback(
    async (projectId: string, payload: UpsertProjectMemoryRequest) => {
      const res = await client.upsertProjectMemory(projectId, payload);
      if (res.ok) {
        const refreshRes = await client.getProjectMemories(projectId);
        if (refreshRes.ok) {
          setMemoriesByProject((prev) => ({ ...prev, [projectId]: refreshRes.data.memories }));
        }
      }
      return res;
    },
    [client],
  );

  const deleteProjectMemory = useCallback(
    async (projectId: string, title: string) => {
      const res = await client.deleteProjectMemory(projectId, title);
      if (res.ok) {
        setMemoriesByProject((prev) => ({
          ...prev,
          [projectId]: (prev[projectId] ?? []).filter((memory) => memory.title !== title),
        }));
      }
      return res;
    },
    [client],
  );

  const normalizedMemoriesByProject = Object.fromEntries(
    Object.entries(memoriesByProject).map(([projectId, memories]) => [
      projectId,
      (memories ?? []).map((memory) => ({
        ...memory,
        createdAt: toDate(memory.createdAt),
        updatedAt: toDate(memory.updatedAt),
      })),
    ]),
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
    projectMemoriesByProject: normalizedMemoriesByProject,
    getProjectMemories,
    upsertProjectMemory,
    deleteProjectMemory,
  };
}
