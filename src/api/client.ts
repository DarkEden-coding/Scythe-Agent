/**
 * ApiClient — configurable HTTP client for the agentic coding back-end.
 *
 * Usage:
 *   const api = new ApiClient({ baseUrl: '/api' });
 *   const history = await api.getChatHistory('chat-1');
 *
 * Features:
 *   - Automatic retry with exponential back-off and jitter
 *   - Configurable retry budget (count, delay, max delay, retryable status codes)
 *   - Per-request AbortController support
 *   - SSE-based real-time agent event streaming
 */

import type {
  ApiResponse,
  SendMessageRequest,
  SendMessageResponse,
  ContinueAgentResponse,
  ApproveCommandRequest,
  ApproveCommandResponse,
  RejectCommandRequest,
  RejectCommandResponse,
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
  EditMessageRequest,
  EditMessageResponse,
  GetPlansResponse,
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
  GetFsChildrenResponse,
  GetChatHistoryResponse,
  GetProjectsResponse,
  GetSettingsResponse,
  AgentEvent,
  OpenRouterConfig,
  GroqConfig,
  BraveConfig,
  OpenAISubConfig,
  OpenAISubAuthStartResponse,
  SetApiKeyRequest,
  SetApiKeyResponse,
  SetSystemPromptRequest,
  SetSystemPromptResponse,
  SetReasoningLevelRequest,
  SetReasoningLevelResponse,
  TestConnectionResponse,
  SyncModelsResponse,
  MemorySettings,
  SetMemorySettingsRequest,
  ChatMemoryStateResponse,
  MCPServersResponse,
  MCPServer,
  MCPTool,
  CreateMCPServerRequest,
  UpdateMCPServerRequest,
  RefreshMCPResponse,
} from './types';

/* ── Retry Configuration ────────────────────────────────────────── */

export interface RetryConfig {
  /** Maximum number of retry attempts (0 = no retries). Default 3. */
  maxRetries: number;
  /** Initial delay in ms before the first retry. Default 500. */
  baseDelay: number;
  /** Maximum delay in ms between retries (caps exponential growth). Default 15 000. */
  maxDelay: number;
  /** Multiplier applied to the delay after each attempt. Default 2. */
  backoffMultiplier: number;
  /** When true, a random jitter of 0–50% of the delay is added. Default true. */
  jitter: boolean;
  /** HTTP status codes that are eligible for retry. Default [408,429,500,502,503,504]. */
  retryableStatusCodes: number[];
  /** If true, network errors (TypeError / AbortError) are retried. Default true. */
  retryOnNetworkError: boolean;
}

const DEFAULT_RETRY: RetryConfig = {
  maxRetries: 3,
  baseDelay: 500,
  maxDelay: 15_000,
  backoffMultiplier: 2,
  jitter: true,
  retryableStatusCodes: [408, 429, 500, 502, 503, 504],
  retryOnNetworkError: true,
};

/* ── Client Configuration ───────────────────────────────────────── */

export interface ApiClientConfig {
  /** Base URL of the API server (e.g. "/api" for proxied requests or "http://localhost:3001/api" for direct). */
  baseUrl: string;
  /** Optional bearer token for authentication. */
  token?: string;
  /** Request timeout in ms. Default 30 000. */
  timeout?: number;
  /** Retry configuration. Merged with defaults. */
  retry?: Partial<RetryConfig>;
  /** Called before each retry — return false to abort the retry chain. */
  onRetry?: (attempt: number, delay: number, error: string, method: string, path: string) => boolean | void;
}

/* ── Client Class ───────────────────────────────────────────────── */

export class ApiClient {
  private config: Required<Omit<ApiClientConfig, 'retry' | 'onRetry'>>;
  private retryConfig: RetryConfig;
  private onRetry?: ApiClientConfig['onRetry'];
  private abortControllers = new Map<string, AbortController>();
  private eventListeners = new Map<string, ((event: AgentEvent) => void)[]>();
  private activeSessions = new Map<string, AbortController>();

  constructor(config: Partial<ApiClientConfig> = {}) {
    this.config = {
      baseUrl: config.baseUrl ?? '/api',
      token: config.token ?? '',
      timeout: config.timeout ?? 30_000,
    };
    this.retryConfig = { ...DEFAULT_RETRY, ...config.retry };
    this.onRetry = config.onRetry;
  }

  /* ── Retry helpers ───────────────────────────────────────────── */

  /** Compute delay for the given attempt (0-indexed). */
  private computeDelay(attempt: number): number {
    const { baseDelay, backoffMultiplier, maxDelay, jitter } = this.retryConfig;
    let delay = baseDelay * Math.pow(backoffMultiplier, attempt);
    delay = Math.min(delay, maxDelay);
    if (jitter) {
      // Add 0-50 % random jitter to decorrelate concurrent retries
      delay += delay * Math.random() * 0.5;
    }
    return Math.round(delay);
  }

  /** Determine whether an HTTP status code is retryable. */
  private isRetryableStatus(status: number): boolean {
    return this.retryConfig.retryableStatusCodes.includes(status);
  }

  /** Determine whether an error is retryable. */
  private isRetryableError(err: unknown): boolean {
    if (!this.retryConfig.retryOnNetworkError) return false;
    if (err instanceof TypeError) return true; // network failure
    if (err instanceof DOMException && err.name === 'AbortError') return false; // user-cancelled
    return true;
  }

  /** Sleep helper (respects abort signal). */
  private sleep(ms: number, signal?: AbortSignal): Promise<void> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(resolve, ms);
      signal?.addEventListener('abort', () => {
        clearTimeout(timer);
        reject(new DOMException('Aborted', 'AbortError'));
      }, { once: true });
    });
  }

  /* ── Private request with retry ──────────────────────────────── */

  private headers(): Record<string, string> {
    const h: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (this.config.token) {
      h['Authorization'] = `Bearer ${this.config.token}`;
    }
    return h;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    requestId?: string,
  ): Promise<ApiResponse<T>> {
    // ── Real HTTP path with retry ──
    const controller = new AbortController();
    if (requestId) {
      this.abortControllers.get(requestId)?.abort();
      this.abortControllers.set(requestId, controller);
    }

    const { maxRetries } = this.retryConfig;
    let lastError = '';

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      // ── Wait before retry (skip on first attempt) ──
      if (attempt > 0) {
        const delay = this.computeDelay(attempt - 1);

        // Notify retry listener — they can abort the chain
        if (this.onRetry) {
          const shouldContinue = this.onRetry(attempt, delay, lastError, method, path);
          if (shouldContinue === false) {
            break;
          }
        }

        try {
          await this.sleep(delay, controller.signal);
        } catch {
          // abort during sleep
          break;
        }
      }

      const timeoutId = setTimeout(() => controller.abort(), this.config.timeout);

      try {
        const res = await fetch(`${this.config.baseUrl}${path}`, {
          method,
          headers: this.headers(),
          body: body ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        // ── Success ──
        if (res.ok) {
          const payload = await res.json();

          // Backend returns envelope: { ok, data, error, timestamp }
          if (
            payload &&
            typeof payload === 'object' &&
            'ok' in payload &&
            'data' in payload
          ) {
            const envelope = payload as ApiResponse<T>;
            return {
              ok: envelope.ok,
              data: envelope.data,
              error: envelope.error,
              timestamp: envelope.timestamp ?? new Date().toISOString(),
            };
          }

          // Fallback for non-enveloped success payloads.
          return { ok: true, data: payload as T, timestamp: new Date().toISOString() };
        }

        // ── Non-retryable HTTP error ──
        if (!this.isRetryableStatus(res.status) || attempt === maxRetries) {
          const errorData = await res.json().catch(() => ({}));
          if (
            errorData &&
            typeof errorData === 'object' &&
            'ok' in errorData &&
            'data' in errorData
          ) {
            const envelope = errorData as ApiResponse<T>;
            return {
              ok: false,
              data: null as unknown as T,
              error: envelope.error ?? `HTTP ${res.status}`,
              timestamp: envelope.timestamp ?? new Date().toISOString(),
            };
          }

          lastError = (errorData as { error?: string }).error ?? `HTTP ${res.status}`;
          return {
            ok: false,
            data: null as unknown as T,
            error: lastError,
            timestamp: new Date().toISOString(),
          };
        }

        // ── Retryable HTTP error — loop continues ──
        const errorData = await res.json().catch(() => ({}));
        lastError = (errorData as { error?: string }).error ?? `HTTP ${res.status}`;
      } catch (err) {
        clearTimeout(timeoutId);

        // User-initiated abort — do not retry
        if (err instanceof DOMException && err.name === 'AbortError') {
          return {
            ok: false,
            data: null as unknown as T,
            error: 'Request aborted',
            timestamp: new Date().toISOString(),
          };
        }

        lastError = err instanceof Error ? err.message : 'Unknown error';

        // Non-retryable network error
        if (!this.isRetryableError(err) || attempt === maxRetries) {
          return {
            ok: false,
            data: null as unknown as T,
            error: lastError,
            timestamp: new Date().toISOString(),
          };
        }

        // Retryable — loop continues
      }
    }

    // Exhausted retries
    if (requestId) this.abortControllers.delete(requestId);
    return {
      ok: false,
      data: null as unknown as T,
      error: `Failed after ${maxRetries + 1} attempts: ${lastError}`,
      timestamp: new Date().toISOString(),
    };
  }

  /** Cancel an in-flight request by its ID. */
  cancel(requestId: string) {
    this.abortControllers.get(requestId)?.abort();
    this.abortControllers.delete(requestId);
  }

  /* ── Concurrent Session Management ───────────────────────────── */

  /**
   * Start an agent session for a chat. Each chat gets its own
   * AbortController so multiple chats can run concurrently.
   * Calling this again for the same chatId aborts the previous session.
   */
  startSession(chatId: string): AbortController {
    this.activeSessions.get(chatId)?.abort();
    const controller = new AbortController();
    this.activeSessions.set(chatId, controller);
    return controller;
  }

  /** End (clean up) an agent session for a chat. */
  endSession(chatId: string): void {
    this.activeSessions.delete(chatId);
  }

  /** Get all currently active chat session IDs. */
  getActiveSessions(): string[] {
    return Array.from(this.activeSessions.keys());
  }

  /** Cancel a specific chat's in-flight session. Aborts the send-message request. */
  cancelSession(chatId: string): void {
    this.activeSessions.get(chatId)?.abort();
    this.activeSessions.delete(chatId);
    this.cancel(`send-${chatId}`);
  }

  /** Cancel all active sessions across all chats. */
  cancelAllSessions(): void {
    this.activeSessions.forEach((controller) => controller.abort());
    this.activeSessions.clear();
  }

  /* ── Actions (client → backend) ──────────────────────────────── */

  /** Send a user message to a chat. Manages a per-chat session so
   *  multiple chats can have concurrent in-flight requests. */
  async sendMessage(req: SendMessageRequest): Promise<ApiResponse<SendMessageResponse>> {
    this.startSession(req.chatId);
    try {
      const res = await this.request<SendMessageResponse>(
        'POST',
        `/chat/${req.chatId}/messages`,
        {
          content: req.content,
          mode: req.mode,
          activePlanId: req.activePlanId,
        },
        `send-${req.chatId}`,
      );
      return res;
    } finally {
      this.endSession(req.chatId);
    }
  }

  /** Continue a paused agent run for a chat without posting a new user message. */
  async continueAgent(chatId: string): Promise<ApiResponse<ContinueAgentResponse>> {
    this.startSession(chatId);
    try {
      return await this.request<ContinueAgentResponse>(
        'POST',
        `/chat/${chatId}/continue`,
        undefined,
        `send-${chatId}`,
      );
    } finally {
      this.endSession(chatId);
    }
  }

  /** Request the backend to cancel the running agent for a chat. Fire-and-forget. */
  cancelChat(chatId: string): void {
    void this.request<{ cancelled: boolean }>('POST', `/chat/${chatId}/cancel`);
  }

  /** Approve a pending tool call. */
  async approveCommand(req: ApproveCommandRequest): Promise<ApiResponse<ApproveCommandResponse>> {
    return this.request('POST', `/chat/${req.chatId}/approve`, { toolCallId: req.toolCallId });
  }

  /** Reject a pending tool call. */
  async rejectCommand(req: RejectCommandRequest): Promise<ApiResponse<RejectCommandResponse>> {
    return this.request('POST', `/chat/${req.chatId}/reject`, {
      toolCallId: req.toolCallId,
      reason: req.reason,
    });
  }

  /** Replace the full set of auto-approve rules. */
  async setAutoApproveRules(req: SetAutoApproveRequest): Promise<ApiResponse<SetAutoApproveResponse>> {
    return this.request('PUT', '/settings/auto-approve', req);
  }

  /** Retrieve current auto-approve rules. */
  async getAutoApproveRules(): Promise<ApiResponse<GetAutoApproveResponse>> {
    return this.request('GET', '/settings/auto-approve');
  }

  /** Change the active model. */
  async changeModel(req: ChangeModelRequest): Promise<ApiResponse<ChangeModelResponse>> {
    return this.request('PUT', '/settings/model', req);
  }

  /** Set or clear sub-agent model override. Pass model: null to inherit main model. */
  async changeSubAgentModel(req: {
    model?: string | null;
    provider?: string | null;
    modelKey?: string | null;
  }): Promise<ApiResponse<GetSettingsResponse>> {
    return this.request('PUT', '/settings/sub-agent-model', req);
  }

  /** Update sub-agent numeric settings. */
  async setSubAgentSettings(req: {
    maxParallelSubAgents?: number;
    subAgentMaxIterations?: number;
  }): Promise<ApiResponse<GetSettingsResponse>> {
    return this.request('PUT', '/settings/sub-agent', req);
  }

  /** Summarize the context window of a chat. */
  async summarizeContext(req: SummarizeContextRequest): Promise<ApiResponse<SummarizeContextResponse>> {
    return this.request('POST', `/chat/${req.chatId}/summarize`);
  }

  /** Revert a chat to a specific checkpoint. */
  async revertToCheckpoint(req: RevertToCheckpointRequest): Promise<ApiResponse<RevertToCheckpointResponse>> {
    return this.request('POST', `/chat/${req.chatId}/revert/${req.checkpointId}`);
  }

  /** Revert a single file edit. */
  async revertFile(req: RevertFileRequest): Promise<ApiResponse<RevertFileResponse>> {
    return this.request('POST', `/chat/${req.chatId}/revert-file/${req.fileEditId}`);
  }

  /** Edit a user message — reverts to the message's checkpoint and re-runs the agent. */
  async editMessage(req: EditMessageRequest): Promise<ApiResponse<EditMessageResponse>> {
    return this.request('PUT', `/chat/${req.chatId}/messages/${req.messageId}`, { content: req.content });
  }

  async getPlans(chatId: string): Promise<ApiResponse<GetPlansResponse>> {
    return this.request('GET', `/chat/${chatId}/plans`);
  }

  async getPlan(chatId: string, planId: string): Promise<ApiResponse<GetPlanResponse>> {
    return this.request('GET', `/chat/${chatId}/plans/${planId}`);
  }

  async updatePlan(req: UpdatePlanRequest): Promise<ApiResponse<UpdatePlanResponse>> {
    return this.request('PUT', `/chat/${req.chatId}/plans/${req.planId}`, {
      content: req.content,
      title: req.title,
      baseRevision: req.baseRevision,
      lastEditor: req.lastEditor,
    });
  }

  async approvePlan(req: ApprovePlanRequest): Promise<ApiResponse<ApprovePlanResponse>> {
    return this.request('POST', `/chat/${req.chatId}/plans/${req.planId}/approve`, {
      action: req.action,
    });
  }

  /* ── Data fetching (backend → frontend) ──────────────────────── */

  /** Fetch complete chat history and all associated agent activity. */
  async getChatHistory(chatId: string): Promise<ApiResponse<GetChatHistoryResponse>> {
    return this.request('GET', `/chat/${chatId}/history`, undefined, `history-${chatId}`);
  }

  /** Fetch debug dump (prompts, assembled messages, full history) for the conversation. */
  async getChatDebug(chatId: string): Promise<ApiResponse<Record<string, unknown>>> {
    return this.request('GET', `/chat/${chatId}/debug`, undefined, `debug-${chatId}`);
  }

  /** Fetch all projects and their chats. */
  async getProjects(): Promise<ApiResponse<GetProjectsResponse>> {
    return this.request('GET', '/projects', undefined, 'projects');
  }

  async createProject(req: CreateProjectRequest): Promise<ApiResponse<CreateProjectResponse>> {
    return this.request('POST', '/projects', req);
  }

  async updateProject(projectId: string, req: UpdateProjectRequest): Promise<ApiResponse<UpdateProjectResponse>> {
    return this.request('PATCH', `/projects/${projectId}`, req);
  }

  async deleteProject(projectId: string): Promise<ApiResponse<DeleteProjectResponse>> {
    return this.request('DELETE', `/projects/${projectId}`);
  }

  async reorderProjects(req: ReorderProjectsRequest): Promise<ApiResponse<GetProjectsResponse>> {
    return this.request('PATCH', '/projects/reorder', req);
  }

  async createChat(req: CreateChatRequest): Promise<ApiResponse<CreateChatResponse>> {
    const body = req.title != null && req.title !== '' ? { title: req.title } : {};
    return this.request('POST', `/projects/${req.projectId}/chats`, body);
  }

  async updateChat(req: UpdateChatRequest): Promise<ApiResponse<UpdateChatResponse>> {
    return this.request('PATCH', `/chats/${req.chatId}`, {
      title: req.title,
      isPinned: req.isPinned,
    });
  }

  async deleteChat(req: DeleteChatRequest): Promise<ApiResponse<DeleteChatResponse>> {
    return this.request('DELETE', `/chats/${req.chatId}`);
  }

  async reorderChats(req: ReorderChatsRequest): Promise<ApiResponse<GetProjectsResponse>> {
    return this.request('PATCH', `/projects/${req.projectId}/chats/reorder`, { chatIds: req.chatIds });
  }

  async getFsChildren(path?: string): Promise<ApiResponse<GetFsChildrenResponse>> {
    const query = path ? `?path=${encodeURIComponent(path)}` : '';
    return this.request('GET', `/fs/children${query}`);
  }

  /** Fetch global settings (model, limits, auto-approve rules). */
  async getSettings(): Promise<ApiResponse<GetSettingsResponse>> {
    return this.request('GET', '/settings', undefined, 'settings');
  }

  /* ── OpenRouter configuration ────────────────────────────────── */

  /** Get OpenRouter configuration (masked API key, connection status, model count). */
  async getOpenRouterConfig(): Promise<ApiResponse<OpenRouterConfig>> {
    return this.request('GET', '/settings/openrouter');
  }

  /** Set OpenRouter API key and trigger model sync. */
  async setOpenRouterApiKey(req: SetApiKeyRequest): Promise<ApiResponse<SetApiKeyResponse>> {
    return this.request('PUT', '/settings/openrouter/api-key', req);
  }

  /** Test connection to OpenRouter API using stored API key. */
  async testOpenRouterConnection(): Promise<ApiResponse<TestConnectionResponse>> {
    return this.request('POST', '/settings/openrouter/test');
  }

  /** Manually trigger OpenRouter model sync. */
  async syncOpenRouterModels(): Promise<ApiResponse<SyncModelsResponse>> {
    return this.request('POST', '/settings/openrouter/sync');
  }

  /* ── Groq configuration ────────────────────────────────────────── */

  /** Get Groq configuration (masked API key, connection status, model count). */
  async getGroqConfig(): Promise<ApiResponse<GroqConfig>> {
    return this.request('GET', '/settings/groq');
  }

  /** Set Groq API key and trigger model sync. */
  async setGroqApiKey(req: SetApiKeyRequest): Promise<ApiResponse<SetApiKeyResponse>> {
    return this.request('PUT', '/settings/groq/api-key', req);
  }

  /** Test connection to Groq API using stored API key. */
  async testGroqConnection(): Promise<ApiResponse<TestConnectionResponse>> {
    return this.request('POST', '/settings/groq/test');
  }

  /** Manually trigger Groq model sync. */
  async syncGroqModels(): Promise<ApiResponse<SyncModelsResponse>> {
    return this.request('POST', '/settings/groq/sync');
  }

  /* ── Brave Search configuration ───────────────────────────────── */

  /** Get Brave configuration (masked API key, connection status). */
  async getBraveConfig(): Promise<ApiResponse<BraveConfig>> {
    return this.request('GET', '/settings/brave');
  }

  /** Set Brave API key (encrypted). */
  async setBraveApiKey(req: SetApiKeyRequest): Promise<ApiResponse<SetApiKeyResponse>> {
    return this.request('PUT', '/settings/brave/api-key', req);
  }

  /* ── OpenAI Subscription configuration ───────────────────────── */

  /** Get OpenAI Subscription config (OAuth status, model count). */
  async getOpenAISubConfig(): Promise<ApiResponse<OpenAISubConfig>> {
    return this.request('GET', '/settings/openai-sub');
  }

  /** Start OAuth flow: get auth URL to open in browser. */
  async getOpenAISubAuthStart(): Promise<
    ApiResponse<OpenAISubAuthStartResponse>
  > {
    return this.request('GET', '/settings/openai-sub/auth/start');
  }

  /** Test connection using stored OAuth token. */
  async testOpenAISubConnection(): Promise<
    ApiResponse<TestConnectionResponse>
  > {
    return this.request('POST', '/settings/openai-sub/test');
  }

  /** Manually trigger OpenAI Subscription model sync. */
  async syncOpenAISubModels(): Promise<ApiResponse<SyncModelsResponse>> {
    return this.request('POST', '/settings/openai-sub/sync');
  }

  /** Set custom system prompt. Empty string resets to default. */
  async setSystemPrompt(req: SetSystemPromptRequest): Promise<ApiResponse<SetSystemPromptResponse>> {
    return this.request('PUT', '/settings/system-prompt', req);
  }

  /** Set preferred reasoning level for supported models. */
  async setReasoningLevel(
    req: SetReasoningLevelRequest,
  ): Promise<ApiResponse<SetReasoningLevelResponse>> {
    return this.request('PUT', '/settings/reasoning-level', req);
  }

  /* ── Memory / Observational Memory settings ──────────────────── */

  /** Get memory mode and OM configuration. */
  async getMemorySettings(): Promise<ApiResponse<MemorySettings>> {
    return this.request('GET', '/settings/memory');
  }

  /** Update memory mode and OM configuration. */
  async setMemorySettings(req: SetMemorySettingsRequest): Promise<ApiResponse<MemorySettings>> {
    return this.request('POST', '/settings/memory', req);
  }

  /** Get current memory state for a chat. */
  async getMemoryState(chatId: string): Promise<ApiResponse<ChatMemoryStateResponse>> {
    return this.request('GET', `/chat/${chatId}/memory`);
  }

  /** Retry the active memory cycle for a chat. */
  async retryMemory(chatId: string): Promise<ApiResponse<{ scheduled: boolean }>> {
    return this.request('POST', `/chat/${chatId}/memory/retry`);
  }

  /* ── MCP configuration ──────────────────────────────────────── */

  /** List all MCP servers with their tools. */
  async getMcpServers(): Promise<ApiResponse<MCPServersResponse>> {
    return this.request('GET', '/settings/mcp');
  }

  /** Create a new MCP server. */
  async createMcpServer(req: CreateMCPServerRequest): Promise<ApiResponse<MCPServer>> {
    return this.request('POST', '/settings/mcp', req);
  }

  /** Update an MCP server. */
  async updateMcpServer(serverId: string, req: UpdateMCPServerRequest): Promise<ApiResponse<MCPServer>> {
    return this.request('PUT', `/settings/mcp/${serverId}`, req);
  }

  /** Delete an MCP server. */
  async deleteMcpServer(serverId: string): Promise<ApiResponse<{ deleted: boolean }>> {
    return this.request('DELETE', `/settings/mcp/${serverId}`);
  }

  /** Enable or disable an MCP server. */
  async setMcpServerEnabled(serverId: string, enabled: boolean): Promise<ApiResponse<MCPServer>> {
    return this.request('PATCH', `/settings/mcp/${serverId}/enabled`, { enabled });
  }

  /** Enable or disable an MCP tool. */
  async setMcpToolEnabled(toolId: string, enabled: boolean): Promise<ApiResponse<MCPTool>> {
    return this.request('PATCH', `/settings/mcp/tools/${toolId}/enabled`, { enabled });
  }

  /** Refresh MCP tools from all enabled servers and update the tool registry. */
  async refreshMcpTools(): Promise<ApiResponse<RefreshMCPResponse>> {
    return this.request('POST', '/settings/mcp/refresh');
  }

  /* ── Agent event stream (SSE / WebSocket) ────────────────────── */

  /**
   * Subscribe to real-time agent events for a chat.
   * Returns an unsubscribe function.
   *
   * This connects to an SSE endpoint with automatic reconnection and
   * exponential back-off on failure.
   */
  subscribeToAgentEvents(
    chatId: string,
    callback: (event: AgentEvent) => void,
  ): () => void {
    let cancelled = false;
    let reconnectAttempt = 0;

    const connect = () => {
      if (cancelled) return;

      const url = `${this.config.baseUrl}/chat/${chatId}/events`;
      const eventSource = new EventSource(url);

      eventSource.onopen = () => {
        // Reset back-off on successful connection
        reconnectAttempt = 0;
      };

      eventSource.onmessage = (e) => {
        try {
          const event: AgentEvent = JSON.parse(e.data);
          // Defer callback to avoid [Violation] long-running handler
          queueMicrotask(() => callback(event));
        } catch {
          // skip malformed events
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        if (cancelled) return;

        // Reconnect with exponential back-off
        const delay = this.computeDelay(reconnectAttempt);
        reconnectAttempt = Math.min(reconnectAttempt + 1, 10);
        setTimeout(connect, delay);
      };

      // Store reference for cleanup
      const list = this.eventListeners.get(chatId) || [];
      list.push(callback);
      this.eventListeners.set(chatId, list);

      // Override cleanup for this specific connection
      cleanupRef.close = () => {
        eventSource.close();
      };
    };

    const cleanupRef = { close: () => {} };

    connect();

    return () => {
      cancelled = true;
      cleanupRef.close();
      const remaining = (this.eventListeners.get(chatId) || []).filter((l) => l !== callback);
      this.eventListeners.set(chatId, remaining);
    };
  }
}

/* ── Singleton default instance ────────────────────────────────── */

export const api = new ApiClient();
