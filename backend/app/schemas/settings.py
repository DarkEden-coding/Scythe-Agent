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


class GetSettingsResponse(BaseModel):
    model: str
    availableModels: list[str]
    modelsByProvider: dict[str, list[str]]
    modelMetadata: dict[str, ModelMetadata]
    contextLimit: int
    autoApproveRules: list[AutoApproveRuleOut]
    systemPrompt: str


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
