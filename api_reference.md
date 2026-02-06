# API Reference — Agentic Coding Interface

> **Version:** 1.0.0  
> **Base URL:** `http://localhost:3001/api` (configurable)  
> **Auth:** Bearer token via `Authorization` header  
> **Content-Type:** `application/json` for all request/response bodies  
> **Real-time:** Server-Sent Events (SSE) for agent event streaming

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Client Configuration](#client-configuration)
4. [Retry Logic & Back-off](#retry-logic--back-off)
5. [Response Envelope](#response-envelope)
6. [Endpoints — Client Actions](#endpoints--client-actions)
   - [Send Message](#1-send-message)
   - [Approve Command](#2-approve-command)
   - [Reject Command](#3-reject-command)
   - [Set Auto-Approve Rules](#4-set-auto-approve-rules)
   - [Get Auto-Approve Rules](#5-get-auto-approve-rules)
   - [Change Model](#6-change-model)
   - [Summarize Context](#7-summarize-context)
   - [Revert to Checkpoint](#8-revert-to-checkpoint)
   - [Revert File](#9-revert-file)
7. [Endpoints — Data Fetching](#endpoints--data-fetching)
   - [Get Chat History](#10-get-chat-history)
   - [Get Projects](#11-get-projects)
   - [Get Settings](#12-get-settings)
8. [Real-time Events (SSE)](#real-time-events-sse)
9. [Data Models](#data-models)
10. [React Hooks](#react-hooks)
11. [Error Handling](#error-handling)
12. [Mock Server](#mock-server)
13. [Examples](#examples)

---

## Overview

The API serves a two-panel agentic coding interface:

- **Left panel (Chat):** User ↔ agent conversation with checkpoints and reversion
- **Right panel (Agent Activity):** Tool calls, file edits, reasoning blocks with diffs and approval workflows

The system supports:
- Sending and receiving messages in a chat session
- Approving or rejecting agent tool calls before they execute
- Configuring auto-approve rules to skip manual approval for trusted operations
- Switching between LLM models at runtime
- Summarizing the context window to reclaim token budget
- Reverting to any previous checkpoint (rolling back messages, tool calls, file edits, and reasoning)
- Reverting individual file edits
- Browsing projects (directories) and their associated chat sessions
- Receiving real-time agent events via SSE

---

## Architecture

```
┌──────────────────┐         ┌──────────────────┐
│   React Front-end │◄──SSE──│   Backend Server  │
│                  │         │                  │
│  ApiClient       │──HTTP──►│  /api/*          │
│  React Hooks     │         │                  │
│  Components      │         │  Agent Engine     │
└──────────────────┘         └──────────────────┘
```

### File Structure

```
src/api/
├── types.ts      # All request/response TypeScript interfaces
├── client.ts     # ApiClient class (HTTP, retry, mock, SSE)
├── hooks.ts      # React hooks wrapping the client
└── index.ts      # Barrel re-export
```

---

## Client Configuration

```typescript
import { ApiClient } from './api/client';

const api = new ApiClient({
  baseUrl: 'http://localhost:3001/api',  // API server URL
  token: 'your-bearer-token',            // Optional auth token
  timeout: 30_000,                        // Request timeout (ms)
  useMock: false,                         // true = use built-in mock server
  retry: {
    maxRetries: 3,                        // Max retry attempts
    baseDelay: 500,                       // Initial retry delay (ms)
    maxDelay: 15_000,                     // Maximum retry delay (ms)
    backoffMultiplier: 2,                 // Exponential multiplier
    jitter: true,                         // Add random jitter
    retryableStatusCodes: [408, 429, 500, 502, 503, 504],
    retryOnNetworkError: true,
  },
  onRetry: (attempt, delay, error, method, path) => {
    console.warn(`Retry #${attempt} for ${method} ${path} in ${delay}ms: ${error}`);
    return true; // return false to abort retry chain
  },
});
```

### Configuration Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `baseUrl` | `string` | `"/api"` | Base URL for all API requests |
| `token` | `string` | `""` | Bearer token sent in `Authorization` header |
| `timeout` | `number` | `30000` | Per-attempt timeout in milliseconds |
| `useMock` | `boolean` | `true` | Use built-in mock server (no real HTTP) |
| `retry` | `Partial<RetryConfig>` | See below | Retry configuration (merged with defaults) |
| `onRetry` | `function` | `undefined` | Callback invoked before each retry attempt |

---

## Retry Logic & Back-off

Every HTTP request made by `ApiClient` is wrapped in retry logic with configurable exponential back-off and jitter.

### How It Works

1. **First attempt** executes immediately with the configured `timeout`.
2. **On failure**, the client checks if the error is retryable:
   - HTTP status codes in `retryableStatusCodes` (default: `408, 429, 500, 502, 503, 504`)
   - Network errors (`TypeError` from `fetch`) if `retryOnNetworkError` is `true`
   - **NOT retried:** User-initiated aborts (`AbortError`), `4xx` client errors (except `408` and `429`)
3. **Delay computation** for attempt `n` (0-indexed):
   ```
   delay = min(baseDelay × backoffMultiplier^n, maxDelay)
   if jitter: delay += delay × random(0, 0.5)
   ```
4. **`onRetry` callback** fires before sleeping — return `false` to abort.
5. After `maxRetries` failed retries, the final error is returned.

### Retry Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `maxRetries` | `number` | `3` | Maximum retry attempts (0 = no retries) |
| `baseDelay` | `number` | `500` | Initial delay before first retry (ms) |
| `maxDelay` | `number` | `15000` | Maximum delay cap (ms) |
| `backoffMultiplier` | `number` | `2` | Multiplier per attempt |
| `jitter` | `boolean` | `true` | Add 0–50% random jitter to delay |
| `retryableStatusCodes` | `number[]` | `[408,429,500,502,503,504]` | HTTP codes that trigger retry |
| `retryOnNetworkError` | `boolean` | `true` | Retry on `TypeError` (network failure) |

### Delay Schedule (defaults, without jitter)

| Attempt | Delay |
|---------|-------|
| 1st retry | 500 ms |
| 2nd retry | 1 000 ms |
| 3rd retry | 2 000 ms |
| 4th retry | 4 000 ms |
| 5th retry | 8 000 ms |
| 6th retry | 15 000 ms (capped) |

### SSE Reconnection

The SSE event stream (`subscribeToAgentEvents`) uses the same exponential back-off for reconnection on connection failure, capped at 10 reconnection attempts.

---

## Response Envelope

Every API response is wrapped in a standard envelope:

```typescript
interface ApiResponse<T> {
  ok: boolean;       // true if request succeeded
  data: T;           // Response payload (null on error)
  error?: string;    // Error message (only present when ok=false)
  timestamp: string; // ISO 8601 timestamp of the response
}
```

### Success Example

```json
{
  "ok": true,
  "data": { "model": "Claude Opus 4", "previousModel": "Claude Sonnet 4", "contextLimit": 200000 },
  "timestamp": "2025-01-15T10:30:00.000Z"
}
```

### Error Example

```json
{
  "ok": false,
  "data": null,
  "error": "Failed after 4 attempts: HTTP 503",
  "timestamp": "2025-01-15T10:30:05.000Z"
}
```

---

## Endpoints — Client Actions

These endpoints are called by the front-end to perform user-initiated actions.

---

### 1. Send Message

Send a user message to a chat session.

| | |
|---|---|
| **Method** | `POST` |
| **Path** | `/chat/{chatId}/messages` |
| **Client method** | `api.sendMessage(req)` |

#### Request

```typescript
interface SendMessageRequest {
  chatId: string;    // Target chat session ID
  content: string;   // Message text content
}
```

```json
{
  "content": "Add dark mode support to the Dashboard component"
}
```

#### Response

```typescript
interface SendMessageResponse {
  message: Message;           // The created message object
  checkpoint?: Checkpoint;    // Checkpoint created after this message (optional)
}
```

```json
{
  "ok": true,
  "data": {
    "message": {
      "id": "msg-1705312200000",
      "role": "user",
      "content": "Add dark mode support to the Dashboard component",
      "timestamp": "2025-01-15T10:30:00.000Z"
    },
    "checkpoint": {
      "id": "cp-4",
      "messageId": "msg-1705312200000",
      "label": "User request: dark mode",
      "timestamp": "2025-01-15T10:30:00.000Z",
      "toolCalls": [],
      "fileEdits": [],
      "reasoningBlocks": []
    }
  },
  "timestamp": "2025-01-15T10:30:00.000Z"
}
```

---

### 2. Approve Command

Approve a pending tool call so the agent can execute it.

| | |
|---|---|
| **Method** | `POST` |
| **Path** | `/chat/{chatId}/approve` |
| **Client method** | `api.approveCommand(req)` |

#### Request

```typescript
interface ApproveCommandRequest {
  chatId: string;      // Chat session ID
  toolCallId: string;  // ID of the pending tool call
}
```

```json
{
  "toolCallId": "tc-pending-1"
}
```

#### Response

```typescript
interface ApproveCommandResponse {
  toolCall: ToolCall;      // Updated tool call (status: "completed")
  fileEdits: FileEdit[];   // File edits produced by execution
}
```

```json
{
  "ok": true,
  "data": {
    "toolCall": {
      "id": "tc-pending-1",
      "name": "edit_file",
      "status": "completed",
      "input": { "path": "src/components/Dashboard.tsx" },
      "output": "Edit applied successfully",
      "timestamp": "2025-01-15T10:30:05.000Z",
      "duration": 142
    },
    "fileEdits": [
      {
        "id": "fe-13",
        "filePath": "src/components/Dashboard.tsx",
        "action": "modified",
        "diff": "@@ -1,5 +1,8 @@\n+import { useTheme } from '../hooks/useTheme';\n ...",
        "timestamp": "2025-01-15T10:30:05.000Z",
        "checkpointId": "cp-3"
      }
    ]
  },
  "timestamp": "2025-01-15T10:30:05.000Z"
}
```

---

### 3. Reject Command

Reject a pending tool call and optionally provide a reason.

| | |
|---|---|
| **Method** | `POST` |
| **Path** | `/chat/{chatId}/reject` |
| **Client method** | `api.rejectCommand(req)` |

#### Request

```typescript
interface RejectCommandRequest {
  chatId: string;
  toolCallId: string;
  reason?: string;       // Optional rejection reason shown to agent
}
```

```json
{
  "toolCallId": "tc-pending-1",
  "reason": "Use a CSS variable approach instead of a hook"
}
```

#### Response

```typescript
interface RejectCommandResponse {
  toolCallId: string;
  status: "rejected";
}
```

---

### 4. Set Auto-Approve Rules

Replace the full set of auto-approve rules. Each rule defines a pattern that, when matched, automatically approves future tool calls without user confirmation.

| | |
|---|---|
| **Method** | `PUT` |
| **Path** | `/settings/auto-approve` |
| **Client method** | `api.setAutoApproveRules(req)` |

#### Request

```typescript
interface SetAutoApproveRequest {
  rules: Array<{
    field: "tool" | "path" | "extension" | "directory" | "pattern";
    value: string;     // Value to match (e.g. "edit_file", ".tsx", "src/components")
    enabled: boolean;  // Whether the rule is active
  }>;
}
```

```json
{
  "rules": [
    { "field": "tool", "value": "read_file", "enabled": true },
    { "field": "extension", "value": ".tsx", "enabled": true },
    { "field": "directory", "value": "src/components", "enabled": true },
    { "field": "tool", "value": "delete_file", "enabled": false }
  ]
}
```

#### Response

```typescript
interface SetAutoApproveResponse {
  rules: AutoApproveRule[];  // Saved rules with generated IDs and timestamps
}
```

#### Auto-Approve Rule Fields

| Field | Match Logic | Example Value |
|-------|-------------|---------------|
| `tool` | Exact match on tool name | `"edit_file"`, `"read_file"` |
| `path` | Exact match on file path | `"src/App.tsx"` |
| `extension` | Match file extension | `".tsx"`, `".css"` |
| `directory` | Match directory prefix | `"src/components"` |
| `pattern` | Glob / regex pattern | `"src/**/*.test.ts"` |

---

### 5. Get Auto-Approve Rules

Retrieve the current set of auto-approve rules.

| | |
|---|---|
| **Method** | `GET` |
| **Path** | `/settings/auto-approve` |
| **Client method** | `api.getAutoApproveRules()` |

#### Response

```typescript
interface GetAutoApproveResponse {
  rules: AutoApproveRule[];
}
```

---

### 6. Change Model

Switch the active LLM model. May affect context window limits.

| | |
|---|---|
| **Method** | `PUT` |
| **Path** | `/settings/model` |
| **Client method** | `api.changeModel(req)` |

#### Request

```typescript
interface ChangeModelRequest {
  model: string;  // Model identifier
}
```

```json
{
  "model": "Claude Opus 4"
}
```

#### Response

```typescript
interface ChangeModelResponse {
  model: string;          // New active model
  previousModel: string;  // Model that was replaced
  contextLimit: number;   // New context window token limit
}
```

```json
{
  "ok": true,
  "data": {
    "model": "Claude Opus 4",
    "previousModel": "Claude Sonnet 4",
    "contextLimit": 200000
  },
  "timestamp": "2025-01-15T10:30:00.000Z"
}
```

---

### 7. Summarize Context

Compress the context window of a chat by summarizing older conversation turns and tool outputs while preserving file contents.

| | |
|---|---|
| **Method** | `POST` |
| **Path** | `/chat/{chatId}/summarize` |
| **Client method** | `api.summarizeContext(req)` |

#### Request

```typescript
interface SummarizeContextRequest {
  chatId: string;
}
```

#### Response

```typescript
interface SummarizeContextResponse {
  contextItems: ContextItem[];  // Updated context items with reduced token counts
  tokensBefore: number;         // Total tokens before summarization
  tokensAfter: number;          // Total tokens after summarization
}
```

```json
{
  "ok": true,
  "data": {
    "contextItems": [ ... ],
    "tokensBefore": 89400,
    "tokensAfter": 42100
  },
  "timestamp": "2025-01-15T10:30:00.000Z"
}
```

---

### 8. Revert to Checkpoint

Roll back all state (messages, tool calls, file edits, reasoning blocks) to a specific checkpoint. All data created after the checkpoint is discarded.

| | |
|---|---|
| **Method** | `POST` |
| **Path** | `/chat/{chatId}/revert/{checkpointId}` |
| **Client method** | `api.revertToCheckpoint(req)` |

#### Request

```typescript
interface RevertToCheckpointRequest {
  chatId: string;
  checkpointId: string;
}
```

#### Response

```typescript
interface RevertToCheckpointResponse {
  messages: Message[];               // Messages up to and including the checkpoint
  toolCalls: ToolCall[];             // Tool calls up to the checkpoint
  fileEdits: FileEdit[];             // File edits up to the checkpoint
  checkpoints: Checkpoint[];         // Checkpoints up to and including the target
  reasoningBlocks: ReasoningBlock[]; // Reasoning blocks up to the checkpoint
}
```

> **Important:** This is a destructive operation. The front-end replaces its entire state with the response data.

---

### 9. Revert File

Undo a single file edit without rolling back the entire checkpoint.

| | |
|---|---|
| **Method** | `POST` |
| **Path** | `/chat/{chatId}/revert-file/{fileEditId}` |
| **Client method** | `api.revertFile(req)` |

#### Request

```typescript
interface RevertFileRequest {
  chatId: string;
  fileEditId: string;
}
```

#### Response

```typescript
interface RevertFileResponse {
  removedFileEditId: string;  // ID of the removed file edit
  fileEdits: FileEdit[];      // Updated list of all remaining file edits
}
```

---

## Endpoints — Data Fetching

These endpoints fetch state from the backend to hydrate the front-end.

---

### 10. Get Chat History

Fetch the complete history and all agent activity for a specific chat session. This is the primary hydration endpoint called when loading a chat.

| | |
|---|---|
| **Method** | `GET` |
| **Path** | `/chat/{chatId}/history` |
| **Client method** | `api.getChatHistory(chatId)` |
| **Request ID** | `history-{chatId}` (auto-cancels previous in-flight request for same chat) |

#### Response

```typescript
interface GetChatHistoryResponse {
  chatId: string;
  messages: Message[];
  toolCalls: ToolCall[];
  fileEdits: FileEdit[];
  checkpoints: Checkpoint[];
  reasoningBlocks: ReasoningBlock[];
  contextItems: ContextItem[];
  maxTokens: number;           // Context window token limit
  model: string;               // Active model for this chat
}
```

#### Notes

- **Messages** include both `user` and `assistant` roles, ordered chronologically.
- **Checkpoints** reference messages by `messageId` and contain lists of `toolCalls`, `fileEdits`, and `reasoningBlocks` IDs that belong to that checkpoint.
- **Context items** represent what's currently in the model's context window (files, conversation history, tool outputs, summaries).

---

### 11. Get Projects

Fetch all projects (directories) and their associated chat sessions.

| | |
|---|---|
| **Method** | `GET` |
| **Path** | `/projects` |
| **Client method** | `api.getProjects()` |
| **Request ID** | `projects` (auto-cancels previous) |

#### Response

```typescript
interface GetProjectsResponse {
  projects: Project[];
}
```

#### Project Structure

```typescript
interface Project {
  id: string;
  name: string;              // Display name (e.g. "dashboard-app")
  path: string;              // Filesystem path (e.g. "~/projects/dashboard-app")
  chats: ProjectChat[];      // Chat sessions within this project
  lastActive: Date;          // Most recent activity timestamp
}

interface ProjectChat {
  id: string;
  title: string;             // Chat title (e.g. "Add dark mode support")
  lastMessage: string;       // Preview of last message
  messageCount: number;
  createdAt: Date;
  updatedAt: Date;
}
```

---

### 12. Get Settings

Fetch global configuration including the active model, available models, context limits, and auto-approve rules.

| | |
|---|---|
| **Method** | `GET` |
| **Path** | `/settings` |
| **Client method** | `api.getSettings()` |
| **Request ID** | `settings` (auto-cancels previous) |

#### Response

```typescript
interface GetSettingsResponse {
  model: string;                       // Currently active model
  availableModels: string[];           // List of selectable models
  contextLimit: number;                // Token limit for context window
  autoApproveRules: AutoApproveRule[]; // Active auto-approve rules
}
```

```json
{
  "ok": true,
  "data": {
    "model": "Claude Sonnet 4",
    "availableModels": [
      "Claude Sonnet 4",
      "Claude Opus 4",
      "Claude Haiku 3.5",
      "GPT-4o",
      "GPT-4.1"
    ],
    "contextLimit": 128000,
    "autoApproveRules": []
  },
  "timestamp": "2025-01-15T10:30:00.000Z"
}
```

---

## Real-time Events (SSE)

The agent streams events to the front-end via Server-Sent Events.

| | |
|---|---|
| **Protocol** | SSE (`text/event-stream`) |
| **URL** | `/chat/{chatId}/events` |
| **Client method** | `api.subscribeToAgentEvents(chatId, callback)` |
| **Reconnection** | Automatic with exponential back-off (same algorithm as HTTP retry) |

### Subscribing

```typescript
const unsubscribe = api.subscribeToAgentEvents('chat-1', (event) => {
  switch (event.type) {
    case 'message':
      // Agent sent a message
      break;
    case 'tool_call_start':
      // Agent started executing a tool
      break;
    case 'approval_required':
      // Agent needs approval before executing
      break;
    // ... handle other event types
  }
});

// Later: clean up
unsubscribe();
```

### Event Envelope

```typescript
interface AgentEvent {
  type: AgentEventType;
  chatId: string;
  timestamp: string;         // ISO 8601
  payload: EventPayload;     // Type depends on `type` field
}
```

### Event Types

| Type | Payload | Description |
|------|---------|-------------|
| `message` | `AgentMessagePayload` | Agent sent a chat message to the user |
| `tool_call_start` | `AgentToolCallPayload` | Agent began executing a tool call |
| `tool_call_end` | `AgentToolCallPayload` | Tool call finished (check `status` for result) |
| `file_edit` | `AgentFileEditPayload` | A file was created, modified, or deleted |
| `reasoning_start` | `AgentReasoningPayload` | Agent began a reasoning/thinking block |
| `reasoning_end` | `AgentReasoningPayload` | Reasoning block completed |
| `checkpoint` | `AgentCheckpointPayload` | A new checkpoint was created |
| `approval_required` | `AgentApprovalPayload` | Agent needs user approval for a tool call |
| `context_update` | `AgentContextPayload` | Context window contents changed |
| `error` | `AgentErrorPayload` | An error occurred in the agent |

### Event Payloads

```typescript
// message
interface AgentMessagePayload {
  message: Message;
}

// tool_call_start, tool_call_end
interface AgentToolCallPayload {
  toolCall: ToolCall;
}

// file_edit
interface AgentFileEditPayload {
  fileEdit: FileEdit;
}

// reasoning_start, reasoning_end
interface AgentReasoningPayload {
  reasoningBlock: ReasoningBlock;
}

// checkpoint
interface AgentCheckpointPayload {
  checkpoint: Checkpoint;
}

// approval_required
interface AgentApprovalPayload {
  toolCallId: string;
  toolName: string;
  input: Record<string, unknown>;
  description: string;
}

// context_update
interface AgentContextPayload {
  contextItems: ContextItem[];
}

// error
interface AgentErrorPayload {
  code: string;
  message: string;
}
```

### SSE Wire Format

Each event is sent as a standard SSE `data` frame with JSON:

```
data: {"type":"message","chatId":"chat-1","timestamp":"2025-01-15T10:30:00.000Z","payload":{"message":{"id":"msg-5","role":"assistant","content":"I've added dark mode.","timestamp":"2025-01-15T10:30:00.000Z"}}}

data: {"type":"tool_call_start","chatId":"chat-1","timestamp":"2025-01-15T10:30:01.000Z","payload":{"toolCall":{"id":"tc-8","name":"edit_file","status":"running","input":{"path":"src/App.tsx"},"timestamp":"2025-01-15T10:30:01.000Z"}}}

data: {"type":"approval_required","chatId":"chat-1","timestamp":"2025-01-15T10:30:02.000Z","payload":{"toolCallId":"tc-9","toolName":"delete_file","input":{"path":"src/old/Legacy.tsx"},"description":"Delete the legacy component file"}}
```

---

## Data Models

### Message

```typescript
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}
```

### ToolCall

```typescript
interface ToolCall {
  id: string;
  name: string;                              // Tool function name (e.g. "edit_file")
  status: 'completed' | 'running' | 'pending' | 'error';
  input: Record<string, unknown>;            // Tool input arguments
  output?: string;                           // Tool output (when completed)
  timestamp: Date;
  duration?: number;                         // Execution time in ms
  checkpointId?: string;                     // Parent checkpoint
  parallel?: boolean;                        // Part of a parallel execution group
  parallelGroup?: string;                    // Group ID for parallel calls
}
```

### FileEdit

```typescript
interface FileEdit {
  id: string;
  filePath: string;                          // File path (e.g. "src/App.tsx")
  action: 'created' | 'modified' | 'deleted';
  diff: string;                              // Unified diff format
  timestamp: Date;
  checkpointId: string;                      // Parent checkpoint
}
```

### Checkpoint

```typescript
interface Checkpoint {
  id: string;
  messageId: string;                         // The user message that triggered this checkpoint
  label: string;                             // Human-readable label
  timestamp: Date;
  toolCalls: string[];                       // IDs of tool calls in this checkpoint
  fileEdits: string[];                       // IDs of file edits in this checkpoint
  reasoningBlocks?: string[];                // IDs of reasoning blocks in this checkpoint
}
```

### ReasoningBlock

```typescript
interface ReasoningBlock {
  id: string;
  content: string;                           // The agent's thinking/reasoning text
  timestamp: Date;
  duration: number;                          // Thinking time in ms
  checkpointId: string;                      // Parent checkpoint
}
```

### ContextItem

```typescript
interface ContextItem {
  id: string;
  type: 'file' | 'conversation' | 'tool_output' | 'summary';
  label: string;                             // Display label
  tokens: number;                            // Token count consumed
}
```

### Project

```typescript
interface Project {
  id: string;
  name: string;                              // Display name
  path: string;                              // Filesystem directory path
  chats: ProjectChat[];
  lastActive: Date;
}

interface ProjectChat {
  id: string;
  title: string;
  lastMessage: string;                       // Preview of the last message
  messageCount: number;
  createdAt: Date;
  updatedAt: Date;
}
```

### AutoApproveRule

```typescript
interface AutoApproveRule {
  id: string;
  field: 'tool' | 'path' | 'extension' | 'directory' | 'pattern';
  value: string;
  enabled: boolean;
  createdAt: string;                         // ISO 8601
}
```

---

## React Hooks

The API provides four React hooks that manage state, loading, and error handling.

### `useChatHistory(chatId, client?)`

Fetches and manages all state for a chat session.

```typescript
const {
  // State
  messages, toolCalls, fileEdits, checkpoints,
  reasoningBlocks, contextItems, maxTokens, model,
  loading, error,

  // Actions (call the API and update local state)
  sendMessage,          // (content: string) => Promise<ApiResponse>
  approveCommand,       // (toolCallId: string) => Promise<ApiResponse>
  rejectCommand,        // (toolCallId: string, reason?: string) => Promise<ApiResponse>
  summarizeContext,     // () => Promise<ApiResponse>
  removeContextItem,    // (itemId: string) => void  (local only)
  revertToCheckpoint,   // (checkpointId: string) => Promise<ApiResponse>
  revertFile,           // (fileEditId: string) => Promise<ApiResponse>

  // Direct setters (for optimistic updates or event handling)
  setMessages, setToolCalls, setFileEdits, setCheckpoints,
  setReasoningBlocks, setContextItems, setModel, setMaxTokens,
} = useChatHistory('chat-1');
```

### `useProjects(client?)`

Fetches all projects.

```typescript
const {
  projects,   // Project[]
  loading,    // boolean
  error,      // string | null
  refresh,    // () => Promise<void>
} = useProjects();
```

### `useSettings(client?)`

Fetches and manages global settings.

```typescript
const {
  settings,             // GetSettingsResponse | null
  loading, error,
  currentModel,         // string
  availableModels,      // string[]
  contextLimit,         // number
  autoApproveRules,     // AutoApproveRule[]
  changeModel,          // (model: string) => Promise<ApiResponse>
  updateAutoApproveRules, // (rules: ...) => Promise<ApiResponse>
  getAutoApproveRules,  // () => Promise<ApiResponse>
} = useSettings();
```

### `useAgentEvents(chatId, onEvent, client?)`

Subscribes to real-time agent events. Automatically cleans up on unmount or `chatId` change.

```typescript
useAgentEvents('chat-1', (event) => {
  if (event.type === 'message') {
    setMessages(prev => [...prev, event.payload.message]);
  }
  if (event.type === 'approval_required') {
    showApprovalDialog(event.payload);
  }
});
```

---

## Error Handling

### HTTP Errors

All errors are returned in the `ApiResponse` envelope — the client never throws.

```typescript
const res = await api.sendMessage({ chatId: 'chat-1', content: 'Hello' });

if (!res.ok) {
  console.error(res.error);
  // "Failed after 4 attempts: HTTP 503"
  // "Request aborted"
  // "Checkpoint not found"
}
```

### Error Categories

| Category | Retried? | Example |
|----------|----------|---------|
| Network failure | Yes (if `retryOnNetworkError`) | `TypeError: Failed to fetch` |
| Timeout | Yes (408) | Request exceeded `timeout` ms |
| Rate limit | Yes (429) | Server rate limiting |
| Server error | Yes (500–504) | Internal server error, bad gateway |
| Client error | **No** | 400 Bad Request, 401 Unauthorized, 404 Not Found |
| User abort | **No** | `api.cancel(requestId)` called |

### Abort / Cancel

```typescript
// Cancel a specific request by its ID
api.cancel('history-chat-1');

// Sending a new request with the same requestId auto-cancels the previous one
await api.getChatHistory('chat-1'); // requestId = "history-chat-1"
await api.getChatHistory('chat-1'); // previous request is aborted
```

### Concurrent Chat Sessions

The client supports multiple chats running concurrently, each with an independent `AbortController` session:

```typescript
// Start a session for a chat (auto-called by sendMessage)
const controller = api.startSession('chat-1');

// End a session cleanly
api.endSession('chat-1');

// Get all currently active chat IDs
const active: string[] = api.getActiveSessions();

// Cancel a specific chat's session
api.cancelSession('chat-1');

// Cancel all active sessions across all chats
api.cancelAllSessions();
```

**`sendMessage()`** automatically manages sessions: it calls `startSession()` before the request and `endSession()` on completion. Calling `startSession()` again for the same `chatId` aborts the previous session. Multiple chats can have concurrent in-flight requests — sending a message in Chat A does not affect Chat B.

#### React Hook: Per-Chat Processing State

The `useChatHistory` hook tracks processing state per chat:

```typescript
const chat = useChatHistory('chat-1');

// Check if the current chat is processing
chat.isChatProcessing();          // boolean

// Check if a specific chat is processing
chat.isChatProcessing('chat-2');  // boolean

// Get all currently processing chat IDs
chat.getProcessingChats();        // string[]

// Cancel processing for current or specific chat
chat.cancelProcessing();
chat.cancelProcessing('chat-2');
```

---

## Mock Server

When `useMock: true` (default), all requests are handled by an in-memory mock server that:

- Returns realistic data from the `mockData.ts` dataset
- Simulates network latency (300–500 ms random delay)
- Handles all 12 endpoints with logical behavior
- Supports revert by filtering data based on checkpoint timestamps
- Supports summarize by reducing token counts on conversation/tool_output items
- Simulates SSE by emitting an `approval_required` event after 1.5 seconds

### Switching to Production

```typescript
const api = new ApiClient({
  baseUrl: 'https://your-api.example.com/api',
  token: process.env.API_TOKEN,
  useMock: false,
  retry: {
    maxRetries: 5,
    baseDelay: 1000,
  },
});
```

---

## Examples

### Example: Full Chat Flow

```typescript
import { ApiClient } from './api/client';

const api = new ApiClient({ baseUrl: '/api', useMock: false });

// 1. Load a chat
const history = await api.getChatHistory('chat-1');
if (!history.ok) throw new Error(history.error);

// 2. Send a message
const msgRes = await api.sendMessage({
  chatId: 'chat-1',
  content: 'Add authentication to the app',
});

// 3. Subscribe to events and wait for approval request
const unsubscribe = api.subscribeToAgentEvents('chat-1', async (event) => {
  if (event.type === 'approval_required') {
    const payload = event.payload as AgentApprovalPayload;

    // 4. Approve the tool call
    await api.approveCommand({
      chatId: 'chat-1',
      toolCallId: payload.toolCallId,
    });
  }

  if (event.type === 'message') {
    const payload = event.payload as AgentMessagePayload;
    console.log('Agent says:', payload.message.content);
  }
});

// 5. Later: revert to a checkpoint
await api.revertToCheckpoint({
  chatId: 'chat-1',
  checkpointId: 'cp-2',
});

// 6. Clean up
unsubscribe();
```

### Example: Auto-Approve Configuration

```typescript
// Set rules to auto-approve read operations and .tsx file edits
await api.setAutoApproveRules({
  rules: [
    { field: 'tool', value: 'read_file', enabled: true },
    { field: 'tool', value: 'list_files', enabled: true },
    { field: 'extension', value: '.tsx', enabled: true },
    { field: 'directory', value: 'src/components', enabled: true },
  ],
});

// Retrieve current rules
const rulesRes = await api.getAutoApproveRules();
console.log(rulesRes.data.rules);
```

### Example: Custom Retry with Logging

```typescript
const api = new ApiClient({
  baseUrl: '/api',
  useMock: false,
  retry: {
    maxRetries: 5,
    baseDelay: 1000,
    maxDelay: 30_000,
    backoffMultiplier: 2.5,
    jitter: true,
    retryableStatusCodes: [429, 500, 502, 503, 504],
    retryOnNetworkError: true,
  },
  onRetry: (attempt, delay, error, method, path) => {
    console.warn(
      `[Retry ${attempt}] ${method} ${path} — waiting ${delay}ms — ${error}`
    );

    // Abort after 5 retries of 429s (rate limit)
    if (error.includes('429') && attempt >= 3) {
      console.error('Rate limited too many times, aborting.');
      return false; // stops retry chain
    }

    return true; // continue retrying
  },
});
```

### Example: Using React Hooks

```tsx
import { useChatHistory, useProjects, useSettings, useAgentEvents } from './api/hooks';

function App() {
  const chat = useChatHistory('chat-1');
  const { projects } = useProjects();
  const { currentModel, changeModel } = useSettings();

  // Handle real-time events
  useAgentEvents('chat-1', (event) => {
    if (event.type === 'message') {
      chat.setMessages(prev => [...prev, (event.payload as any).message]);
    }
    if (event.type === 'tool_call_end') {
      chat.setToolCalls(prev =>
        prev.map(tc =>
          tc.id === (event.payload as any).toolCall.id
            ? (event.payload as any).toolCall
            : tc
        )
      );
    }
  });

  if (chat.loading) return <div>Loading...</div>;

  return (
    <div>
      {chat.messages.map(msg => (
        <div key={msg.id}>{msg.content}</div>
      ))}
      <button onClick={() => chat.sendMessage('Hello!')}>Send</button>
      <button onClick={() => changeModel('Claude Opus 4')}>Switch Model</button>
    </div>
  );
}
```

---

## Endpoint Summary Table

| # | Method | Path | Client Method | Description |
|---|--------|------|---------------|-------------|
| 1 | `POST` | `/chat/{chatId}/messages` | `sendMessage()` | Send a user message |
| 2 | `POST` | `/chat/{chatId}/approve` | `approveCommand()` | Approve a pending tool call |
| 3 | `POST` | `/chat/{chatId}/reject` | `rejectCommand()` | Reject a pending tool call |
| 4 | `PUT` | `/settings/auto-approve` | `setAutoApproveRules()` | Set auto-approve rules |
| 5 | `GET` | `/settings/auto-approve` | `getAutoApproveRules()` | Get auto-approve rules |
| 6 | `PUT` | `/settings/model` | `changeModel()` | Change the active LLM model |
| 7 | `POST` | `/chat/{chatId}/summarize` | `summarizeContext()` | Summarize context window |
| 8 | `POST` | `/chat/{chatId}/revert/{checkpointId}` | `revertToCheckpoint()` | Revert to a checkpoint |
| 9 | `POST` | `/chat/{chatId}/revert-file/{fileEditId}` | `revertFile()` | Revert a single file edit |
| 10 | `GET` | `/chat/{chatId}/history` | `getChatHistory()` | Fetch full chat history |
| 11 | `GET` | `/projects` | `getProjects()` | Fetch all projects |
| 12 | `GET` | `/settings` | `getSettings()` | Fetch global settings |
| — | `SSE` | `/chat/{chatId}/events` | `subscribeToAgentEvents()` | Real-time agent events |
