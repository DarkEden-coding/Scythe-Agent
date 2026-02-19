export interface Message {
  id: string;
  role: 'user' | 'agent';
  content: string;
  timestamp: Date;
  checkpointId?: string;
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

export interface ContextItem {
  id: string;
  type: 'file' | 'conversation' | 'tool_output' | 'summary';
  name: string;
  tokens: number;
  full_name?: string | null;
}

export interface ObservationData {
  hasObservations: boolean;
  generation?: number;
  content?: string;
  tokenCount?: number;
  observedUpToMessageId?: string;
  currentTask?: string;
  suggestedResponse?: string;
  timestamp?: string;
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
