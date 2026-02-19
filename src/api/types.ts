/**
 * API Request & Response Types
 *
 * These types define the full contract between the front-end and any back-end
 * implementation. The ApiClient sends requests shaped like *Request types and
 * expects responses shaped like *Response types.
 */

import {
  Message,
  ToolCall,
  FileEdit,
  Checkpoint,
  ContextItem,
  ReasoningBlock,
  Project,
} from '../types';

/* ── Generic envelope ──────────────────────────────────────────── */

export interface ApiResponse<T> {
  ok: boolean;
  data: T;
  error?: string;
  timestamp: string;
}

/* ── Actions (client → backend) ────────────────────────────────── */

// 1. Send a message
export interface SendMessageRequest {
  chatId: string;
  content: string;
}

export interface SendMessageResponse {
  message: Message;
  /** The checkpoint created after this user message (if any). */
  checkpoint?: Checkpoint;
}

// 2. Approve / reject a pending tool call
export interface ApproveCommandRequest {
  chatId: string;
  toolCallId: string;
}

export interface ApproveCommandResponse {
  toolCall: ToolCall;
  /** Any file edits that resulted from executing the tool. */
  fileEdits: FileEdit[];
}

export interface RejectCommandRequest {
  chatId: string;
  toolCallId: string;
  reason?: string;
}

export interface RejectCommandResponse {
  toolCallId: string;
  status: 'rejected';
}

// 3. Auto-approve rules
export interface AutoApproveRule {
  id: string;
  field: 'tool' | 'path' | 'extension' | 'directory' | 'pattern';
  value: string;
  enabled: boolean;
  createdAt: string;
}

export interface SetAutoApproveRequest {
  rules: Omit<AutoApproveRule, 'id' | 'createdAt'>[];
}

export interface SetAutoApproveResponse {
  rules: AutoApproveRule[];
}

export interface GetAutoApproveResponse {
  rules: AutoApproveRule[];
}

// 4. Change model
export interface ChangeModelRequest {
  model: string;
}

export interface ChangeModelResponse {
  model: string;
  previousModel: string;
  contextLimit: number;
}

// 5. Summarize context
export interface SummarizeContextRequest {
  chatId: string;
}

export interface SummarizeContextResponse {
  contextItems: ContextItem[];
  tokensBefore: number;
  tokensAfter: number;
}

// 6. Revert
export interface RevertToCheckpointRequest {
  chatId: string;
  checkpointId: string;
}

export interface RevertToCheckpointResponse {
  messages: Message[];
  toolCalls: ToolCall[];
  fileEdits: FileEdit[];
  checkpoints: Checkpoint[];
  reasoningBlocks: ReasoningBlock[];
}

export interface RevertFileRequest {
  chatId: string;
  fileEditId: string;
}

export interface RevertFileResponse {
  removedFileEditId: string;
  fileEdits: FileEdit[];
}

// 7. Edit message
export interface EditMessageRequest {
  chatId: string;
  messageId: string;
  content: string;
}

export interface EditMessageResponse {
  revertedHistory: RevertToCheckpointResponse;
}

// 7. Project and chat management
export interface CreateProjectRequest {
  name: string;
  path: string;
}

export interface CreateProjectResponse {
  project: Project;
}

export interface UpdateProjectRequest {
  name?: string;
  path?: string;
}

export interface UpdateProjectResponse {
  project: Project;
}

export interface DeleteProjectResponse {
  deletedProjectId: string;
}

export interface ReorderProjectsRequest {
  projectIds: string[];
}

export interface CreateChatRequest {
  projectId: string;
  title?: string;
}

export interface CreateChatResponse {
  chat: import('../types').ProjectChat;
}

export interface UpdateChatRequest {
  chatId: string;
  title?: string;
  isPinned?: boolean;
}

export interface UpdateChatResponse {
  chat: import('../types').ProjectChat;
}

export interface DeleteChatRequest {
  chatId: string;
}

export interface DeleteChatResponse {
  deletedChatId: string;
  fallbackChatId?: string;
}

export interface ReorderChatsRequest {
  projectId: string;
  chatIds: string[];
}

/* ── Data fetching (backend → frontend) ────────────────────────── */

// 1. Full chat history + agent activity
export interface GetChatHistoryRequest {
  chatId: string;
}

export interface GetChatHistoryResponse {
  chatId: string;
  messages: Message[];
  toolCalls: ToolCall[];
  fileEdits: FileEdit[];
  checkpoints: Checkpoint[];
  reasoningBlocks: ReasoningBlock[];
  contextItems: ContextItem[];
  maxTokens: number;
  model: string;
}

// 2. All projects
export interface GetProjectsResponse {
  projects: Project[];
}

// 3. Filesystem browser
export interface FsChild {
  name: string;
  path: string;
  kind: 'directory' | 'file';
  hasChildren: boolean;
}

export interface GetFsChildrenResponse {
  path: string;
  parentPath: string | null;
  children: FsChild[];
  allowedRoots: string[];
}

// 3. Agent-to-user notifications / streaming
export type AgentEventType =
  | 'message'
  | 'content_delta'
  | 'tool_call_start'
  | 'tool_call_end'
  | 'file_edit'
  | 'reasoning_start'
  | 'reasoning_delta'
  | 'reasoning_end'
  | 'checkpoint'
  | 'approval_required'
  | 'context_update'
  | 'chat_title_updated'
  | 'agent_done'
  | 'message_edited'
  | 'verification_issues'
  | 'observation_status'
  | 'error';

export interface AgentObservationStatusPayload {
  status: 'observing' | 'observed' | 'reflecting' | 'reflected';
  chatId: string;
  tokensSaved?: number;
  tokensBefore?: number;
  tokensAfter?: number;
}

export interface AgentEvent {
  type: AgentEventType;
  chatId: string;
  timestamp: string;
  payload: AgentMessagePayload
    | AgentContentDeltaPayload
    | AgentToolCallPayload
    | AgentFileEditPayload
    | AgentReasoningPayload
    | AgentReasoningDeltaPayload
    | AgentCheckpointPayload
    | AgentApprovalPayload
    | AgentContextPayload
    | AgentChatTitlePayload
    | AgentVerificationIssuesPayload
    | AgentObservationStatusPayload
    | AgentErrorPayload;
}

export interface AgentVerificationIssuesPayload {
  checkpointId: string;
  summary: string;
  issueCount: number;
  fileCount: number;
  byTool?: Record<string, number>;
}

export interface AgentContentDeltaPayload {
  messageId: string;
  delta: string;
}

export interface AgentChatTitlePayload {
  chatId: string;
  title: string;
}

export interface AgentMessagePayload {
  message: Message;
}

export interface AgentToolCallPayload {
  toolCall: ToolCall;
}

export interface AgentFileEditPayload {
  fileEdit: FileEdit;
}

export interface AgentReasoningPayload {
  reasoningBlock: ReasoningBlock;
}

export interface AgentReasoningDeltaPayload {
  reasoningBlockId: string;
  delta: string;
}

export interface AgentCheckpointPayload {
  checkpoint: Checkpoint;
}

export interface AgentApprovalPayload {
  toolCallId: string;
  toolName: string;
  input: Record<string, unknown>;
  description: string;
  autoApproved?: boolean;
}

export interface AgentContextPayload {
  contextItems: ContextItem[];
}

export interface AgentErrorPayload {
  code: string;
  message: string;
}

// 4. Settings
export interface ModelMetadata {
  contextLimit?: number | null;
  pricePerMillion?: number | null;
}

export interface GetSettingsResponse {
  model: string;
  availableModels: string[];
  modelsByProvider: Record<string, string[]>;
  modelMetadata: Record<string, ModelMetadata>;
  contextLimit: number;
  autoApproveRules: AutoApproveRule[];
  systemPrompt: string;
}

export interface SetSystemPromptRequest {
  systemPrompt: string;
}

export interface SetSystemPromptResponse {
  systemPrompt: string;
}

// 5. OpenRouter configuration
export interface OpenRouterConfig {
  apiKeyMasked: string;
  baseUrl: string;
  connected: boolean;
  modelCount: number;
}

// 5b. Groq configuration
export interface GroqConfig {
  apiKeyMasked: string;
  connected: boolean;
  modelCount: number;
}

// 5c. OpenAI Subscription (OAuth) configuration
export interface OpenAISubConfig {
  apiKeyMasked: string;
  connected: boolean;
  modelCount: number;
}

export interface OpenAISubAuthStartResponse {
  authUrl: string;
  state: string;
}

export interface SetApiKeyRequest {
  apiKey: string;
}

export interface SetApiKeyResponse {
  success: boolean;
  modelCount: number;
  error?: string;
}

export interface TestConnectionResponse {
  success: boolean;
  error?: string;
}

export interface SyncModelsResponse {
  success: boolean;
  models: string[];
  count: number;
}

/* ── Memory / Observational Memory settings ───────────────────── */

export interface MemorySettings {
  memory_mode: string;
  observer_model: string | null;
  reflector_model: string | null;
  observer_threshold: number;
  reflector_threshold: number;
  show_observations_in_chat: boolean;
}

export interface SetMemorySettingsRequest {
  memoryMode?: string;
  observerModel?: string;
  reflectorModel?: string;
  observerThreshold?: number;
  reflectorThreshold?: number;
  showObservationsInChat?: boolean;
}

/* ── MCP configuration ────────────────────────────────────────── */

export interface MCPTool {
  id: string;
  serverId: string;
  toolName: string;
  description: string | null;
  enabled: boolean;
  discoveredAt: string;
}

export interface MCPServer {
  id: string;
  name: string;
  transport: string;
  configJson: string;
  enabled: boolean;
  lastConnectedAt: string | null;
  tools: MCPTool[];
}

export interface MCPServersResponse {
  servers: MCPServer[];
}

export interface CreateMCPServerRequest {
  name: string;
  transport: string;
  configJson: string;
}

export interface UpdateMCPServerRequest {
  name?: string;
  transport?: string;
  configJson?: string;
}

export interface RefreshMCPResponse {
  success: boolean;
  discoveredCount: number;
  errors: string[];
}
