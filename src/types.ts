export interface Message {
  id: string;
  role: 'user' | 'agent';
  content: string;
  timestamp: Date;
  checkpointId?: string;
}

export interface SubAgentRun {
  id: string;
  task: string;
  model: string | null;
  status: 'pending' | 'running' | 'completed' | 'error' | 'cancelled' | 'max_iterations';
  output?: string;
  toolCalls: ToolCall[];
  timestamp: Date;
  duration?: number;
  toolCallId: string;
}

export interface ToolCall {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  input: Record<string, unknown>;
  output?: string;
  description?: string;
  approvalRequired?: boolean;
  timestamp: Date;
  duration?: number;
  isParallel?: boolean;
  parallelGroupId?: string;
}

export interface FileEdit {
  id: string;
  filePath: string;
  action: 'create' | 'edit' | 'delete';
  diff?: string;
  timestamp: Date;
  checkpointId: string;
}

export interface Checkpoint {
  id: string;
  messageId: string;
  timestamp: Date;
  label: string;
  fileEdits: string[];
  toolCalls: string[];
  reasoningBlocks?: string[];
}

export interface ReasoningBlock {
  id: string;
  content: string;
  timestamp: Date;
  duration?: number;
  checkpointId: string;
}

export interface TodoItem {
  id: string;
  content: string;
  status: 'pending' | 'in_progress' | 'completed';
  sortOrder: number;
  timestamp: Date;
}

export interface ProjectPlan {
  id: string;
  chatId: string;
  projectId: string;
  checkpointId?: string;
  title: string;
  status: 'drafting' | 'ready' | 'approved' | 'implementing' | 'implemented' | 'error' | string;
  filePath: string;
  revision: number;
  contentSha256: string;
  lastEditor: 'agent' | 'user' | 'external' | string;
  approvedAction?: 'keep_context' | 'clear_context' | string;
  implementationChatId?: string;
  createdAt: Date;
  updatedAt: Date;
  content?: string;
}

export interface ContextItem {
  id: string;
  type: 'file' | 'conversation' | 'tool_output' | 'summary' | 'reasoning';
  name: string;
  tokens: number;
  full_name?: string | null;
}

export interface ObservationData {
  id?: string;
  hasObservations: boolean;
  generation?: number;
  content?: string;
  tokenCount?: number;
  triggerTokenCount?: number;
  observedUpToMessageId?: string;
  observedUpToTimestamp?: string;
  currentTask?: string;
  suggestedResponse?: string;
  timestamp?: string;
  source?: 'stored' | 'buffered';
}

export interface VerificationIssues {
  checkpointId: string;
  summary: string;
  issueCount: number;
  fileCount: number;
  byTool?: Record<string, number>;
}

export interface ProjectChat {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: Date;
  messageCount: number;
  isPinned?: boolean;
  isActive?: boolean;
}

export interface Project {
  id: string;
  name: string;
  path: string;
  lastAccessed: Date;
  sortOrder?: number;
  chats: ProjectChat[];
  isExpanded?: boolean;
}
