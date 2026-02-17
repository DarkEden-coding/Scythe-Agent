from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str
    checkpointId: str | None = None


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


class GetChatHistoryResponse(BaseModel):
    chatId: str
    messages: list[MessageOut]
    toolCalls: list[ToolCallOut]
    fileEdits: list[FileEditOut]
    checkpoints: list[CheckpointOut]
    reasoningBlocks: list[ReasoningBlockOut]
    contextItems: list[ContextItemOut]
    maxTokens: int
    model: str


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)


class SendMessageResponse(BaseModel):
    message: MessageOut
    checkpoint: CheckpointOut | None = None


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
    fileEdits: list[FileEditOut]
    checkpoints: list[CheckpointOut]
    reasoningBlocks: list[ReasoningBlockOut]


class RevertFileResponse(BaseModel):
    removedFileEditId: str
    fileEdits: list[FileEditOut]
