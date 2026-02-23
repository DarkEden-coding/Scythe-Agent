from pydantic import BaseModel, Field


class AutoApproveRuleOut(BaseModel):
    id: str
    field: str
    value: str
    enabled: bool
    createdAt: str


class ModelMetadata(BaseModel):
    contextLimit: int | None = None
    pricePerMillion: float | None = None
    reasoningSupported: bool = False
    reasoningLevels: list[str] = Field(default_factory=list)
    defaultReasoningLevel: str | None = None


class GetSettingsResponse(BaseModel):
    model: str
    modelProvider: str | None = None
    modelKey: str | None = None
    reasoningLevel: str
    availableModels: list[str]
    modelsByProvider: dict[str, list[str]]
    modelMetadata: dict[str, ModelMetadata]
    modelMetadataByKey: dict[str, ModelMetadata]
    contextLimit: int
    autoApproveRules: list[AutoApproveRuleOut]
    systemPrompt: str
    subAgentModel: str | None = None
    subAgentModelProvider: str | None = None
    subAgentModelKey: str | None = None
    maxParallelSubAgents: int = 4
    subAgentMaxIterations: int = 25


class AutoApproveRuleIn(BaseModel):
    field: str = Field(min_length=1)
    value: str = Field(min_length=1)
    enabled: bool


class SetAutoApproveRequest(BaseModel):
    rules: list[AutoApproveRuleIn]


class SetAutoApproveResponse(BaseModel):
    rules: list[AutoApproveRuleOut]


class GetAutoApproveResponse(BaseModel):
    rules: list[AutoApproveRuleOut]


class SetModelRequest(BaseModel):
    model: str = Field(min_length=1, max_length=500)
    provider: str | None = Field(default=None, min_length=1, max_length=64)
    modelKey: str | None = Field(default=None, min_length=3, max_length=600)


class SetSubAgentModelRequest(BaseModel):
    model: str | None = Field(default=None, max_length=500)
    provider: str | None = Field(default=None, min_length=1, max_length=64)
    modelKey: str | None = Field(default=None, min_length=3, max_length=600)


class SetSubAgentSettingsRequest(BaseModel):
    maxParallelSubAgents: int | None = None
    subAgentMaxIterations: int | None = None


class SetModelResponse(BaseModel):
    model: str
    previousModel: str
    contextLimit: int


# OpenRouter configuration schemas
class OpenRouterConfigResponse(BaseModel):
    apiKeyMasked: str
    baseUrl: str
    connected: bool
    modelCount: int


# Groq configuration schemas
class GroqConfigResponse(BaseModel):
    apiKeyMasked: str
    connected: bool
    modelCount: int


class OpenAISubConfigResponse(BaseModel):
    apiKeyMasked: str
    connected: bool
    modelCount: int


class OpenAISubAuthStartResponse(BaseModel):
    authUrl: str
    state: str


class SetApiKeyRequest(BaseModel):
    apiKey: str = Field(min_length=1)


class SetApiKeyResponse(BaseModel):
    success: bool
    modelCount: int
    error: str | None = None


class TestConnectionResponse(BaseModel):
    success: bool
    error: str | None = None


class SyncModelsResponse(BaseModel):
    success: bool
    models: list[str]
    count: int


class SetSystemPromptRequest(BaseModel):
    systemPrompt: str


class SetSystemPromptResponse(BaseModel):
    systemPrompt: str


class SetReasoningLevelRequest(BaseModel):
    reasoningLevel: str = Field(min_length=1, max_length=32)


class SetReasoningLevelResponse(BaseModel):
    reasoningLevel: str


class SetMemorySettingsRequest(BaseModel):
    memoryMode: str | None = None
    observerModel: str | None = None
    reflectorModel: str | None = None
    observerThreshold: int | None = None
    bufferTokens: int | None = None
    reflectorThreshold: int | None = None
    showObservationsInChat: bool | None = None
    toolOutputTokenThreshold: int | None = None
    toolOutputPreviewTokens: int | None = None
