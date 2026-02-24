from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.services.token_counter import count_text_tokens

_MAX_CONTENT_TOKENS = 50_000


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str
    checkpointId: str | None = None


class SubAgentRunOut(BaseModel):
    id: str
    task: str
    model: str | None = None
    status: str
    output: str | None = None
    toolCallId: str
    timestamp: str
    duration: int | None = None
    toolCalls: list[dict] = Field(default_factory=list)


class ToolCallOut(BaseModel):
    id: str
    name: str
    status: str
    input: dict
    output: str | None = None
    timestamp: str
    duration: int | None = None
    isParallel: bool | None = None
    parallelGroupId: str | None = None
    artifacts: list[dict] = Field(default_factory=list)


class FileEditOut(BaseModel):
    id: str
    filePath: str
    action: str
    diff: str | None = None
    timestamp: str
    checkpointId: str


class CheckpointOut(BaseModel):
    id: str
    messageId: str
    timestamp: str
    label: str
    fileEdits: list[str]
    toolCalls: list[str]
    reasoningBlocks: list[str]


class ReasoningBlockOut(BaseModel):
    id: str
    content: str
    timestamp: str
    duration: int | None = None
    checkpointId: str


class ContextItemOut(BaseModel):
    id: str
    type: str
    name: str
    tokens: int
    full_name: str | None = None


class TodoOut(BaseModel):
    id: str
    content: str
    status: str
    sortOrder: int
    timestamp: str


class ProjectPlanOut(BaseModel):
    id: str
    chatId: str
    projectId: str
    checkpointId: str | None = None
    title: str
    status: str
    filePath: str
    revision: int
    contentSha256: str
    lastEditor: str
    approvedAction: str | None = None
    implementationChatId: str | None = None
    createdAt: str
    updatedAt: str
    content: str | None = None


class GetChatHistoryResponse(BaseModel):
    chatId: str
    messages: list[MessageOut]
    toolCalls: list[ToolCallOut]
    subAgentRuns: list[SubAgentRunOut] = Field(default_factory=list)
    fileEdits: list[FileEditOut]
    checkpoints: list[CheckpointOut]
    reasoningBlocks: list[ReasoningBlockOut]
    contextItems: list[ContextItemOut]
    todos: list[TodoOut]
    plans: list[ProjectPlanOut] = Field(default_factory=list)
    maxTokens: int
    model: str


def _validate_content_tokens(v: str) -> str:
    """Validate content does not exceed token limit."""
    tokens = count_text_tokens(v)
    if tokens > _MAX_CONTENT_TOKENS:
        raise ValueError(
            f"Content must be at most {_MAX_CONTENT_TOKENS:,} tokens (got {tokens:,})"
        )
    return v


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def validate_content_tokens(cls, v: str) -> str:
        return _validate_content_tokens(v)

    mode: Literal["default", "planning", "plan_edit"] | None = None
    activePlanId: str | None = None


class SendMessageResponse(BaseModel):
    message: MessageOut
    checkpoint: CheckpointOut | None = None


class ContinueAgentResponse(BaseModel):
    started: bool
    checkpointId: str


class ApproveCommandRequest(BaseModel):
    toolCallId: str = Field(min_length=1)


class ApproveCommandResponse(BaseModel):
    toolCall: ToolCallOut
    fileEdits: list[FileEditOut]


class RejectCommandRequest(BaseModel):
    toolCallId: str = Field(min_length=1)
    reason: str | None = None


class RejectCommandResponse(BaseModel):
    toolCallId: str
    status: str


class SummarizeContextResponse(BaseModel):
    contextItems: list[ContextItemOut]
    tokensBefore: int
    tokensAfter: int


class RevertToCheckpointResponse(BaseModel):
    messages: list[MessageOut]
    toolCalls: list[ToolCallOut]
    subAgentRuns: list[SubAgentRunOut] = Field(default_factory=list)
    fileEdits: list[FileEditOut]
    checkpoints: list[CheckpointOut]
    reasoningBlocks: list[ReasoningBlockOut]
    todos: list[TodoOut]


class RevertFileResponse(BaseModel):
    removedFileEditId: str
    fileEdits: list[FileEditOut]


class EditMessageRequest(BaseModel):
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def validate_content_tokens(cls, v: str) -> str:
        return _validate_content_tokens(v)


class EditMessageResponse(BaseModel):
    revertedHistory: RevertToCheckpointResponse


class UpdatePlanRequest(BaseModel):
    content: str = Field(min_length=1)
    title: str | None = None
    baseRevision: int | None = None
    lastEditor: str | None = None


class UpdatePlanResponse(BaseModel):
    plan: ProjectPlanOut
    conflict: bool = False


class ApprovePlanRequest(BaseModel):
    action: Literal["keep_context", "clear_context"]


class ApprovePlanResponse(BaseModel):
    plan: ProjectPlanOut
    implementationChatId: str | None = None
