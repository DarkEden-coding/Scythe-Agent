from pydantic import BaseModel


class AgentEvent(BaseModel):
    type: str
    chatId: str
    timestamp: str
    payload: dict
    sequence: int | None = None

