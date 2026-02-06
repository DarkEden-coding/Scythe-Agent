from pydantic import BaseModel


class AutoApproveRuleOut(BaseModel):
    id: str
    field: str
    value: str
    enabled: bool
    createdAt: str


class GetSettingsResponse(BaseModel):
    model: str
    availableModels: list[str]
    contextLimit: int
    autoApproveRules: list[AutoApproveRuleOut]


class AutoApproveRuleIn(BaseModel):
    field: str
    value: str
    enabled: bool


class SetAutoApproveRequest(BaseModel):
    rules: list[AutoApproveRuleIn]


class SetAutoApproveResponse(BaseModel):
    rules: list[AutoApproveRuleOut]


class GetAutoApproveResponse(BaseModel):
    rules: list[AutoApproveRuleOut]


class SetModelRequest(BaseModel):
    model: str


class SetModelResponse(BaseModel):
    model: str
    previousModel: str
    contextLimit: int
