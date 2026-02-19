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
  useOpenAISub,
  useAgentEvents,
} from './hooks';

// Types — re-export everything for convenience
export type {
  ApiResponse,
  SendMessageRequest,
  SendMessageResponse,
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
  GetChatHistoryResponse,
  GetProjectsResponse,
  FsChild,
  GetFsChildrenResponse,
  AgentEventType,
  AgentEvent,
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
