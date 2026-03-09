/**
 * API layer barrel export.
 *
 * Usage:
 *   import { api, useChatHistory, useProjects, useSettings, useAgentEvents } from '@/api';
 */

// Client
export { ApiClient, api } from './client';
export type { ApiClientConfig } from './client';

// Hooks
export {
  useChatHistory,
  useProjects,
  useFilesystemBrowser,
  useSettings,
  useOpenRouter,
  useGroq,
  useZAi,
  useOpenAISub,
  useAgentEvents,
} from './hooks';

// Types — re-export everything for convenience
export type {
  ApiResponse,
  SendMessageRequest,
  SendMessageResponse,
  ContinueAgentResponse,
  ApproveCommandRequest,
  ApproveCommandResponse,
  RejectCommandRequest,
  RejectCommandResponse,
  AutoApproveRule,
  SetAutoApproveRequest,
  SetAutoApproveResponse,
  GetAutoApproveResponse,
  ChangeModelRequest,
  ChangeModelResponse,
  SummarizeContextRequest,
  SummarizeContextResponse,
  RevertToCheckpointRequest,
  RevertToCheckpointResponse,
  RevertFileRequest,
  RevertFileResponse,
  GetPlansRequest,
  GetPlansResponse,
  GetPlanRequest,
  GetPlanResponse,
  UpdatePlanRequest,
  UpdatePlanResponse,
  ApprovePlanRequest,
  ApprovePlanResponse,
  CreateProjectRequest,
  CreateProjectResponse,
  UpdateProjectRequest,
  UpdateProjectResponse,
  DeleteProjectResponse,
  ReorderProjectsRequest,
  CreateChatRequest,
  CreateChatResponse,
  UpdateChatRequest,
  UpdateChatResponse,
  DeleteChatRequest,
  DeleteChatResponse,
  ReorderChatsRequest,
  GetProjectMemoriesResponse,
  UpsertProjectMemoryRequest,
  UpsertProjectMemoryResponse,
  DeleteProjectMemoryResponse,
  GetChatHistoryResponse,
  GetProjectsResponse,
  FsChild,
  GetFsChildrenResponse,
  PickDirectoryResponse,
  AgentEventType,
  AgentEvent,
  AgentPausePayload,
  AgentPlanPayload,
  AgentPlanConflictPayload,
  AgentMessagePayload,
  AgentToolCallPayload,
  AgentFileEditPayload,
  AgentReasoningPayload,
  AgentCheckpointPayload,
  AgentApprovalPayload,
  AgentContextPayload,
  AgentErrorPayload,
  GetSettingsResponse,
} from './types';
