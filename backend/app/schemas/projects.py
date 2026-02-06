from pydantic import BaseModel


class ProjectChatOut(BaseModel):
    id: str
    title: str
    lastMessage: str
    timestamp: str
    messageCount: int
    isPinned: bool = False


class ProjectOut(BaseModel):
    id: str
    name: str
    path: str
    lastAccessed: str
    sortOrder: int
    chats: list[ProjectChatOut]


class GetProjectsResponse(BaseModel):
    projects: list[ProjectOut]


class CreateProjectRequest(BaseModel):
    name: str
    path: str


class CreateProjectResponse(BaseModel):
    project: ProjectOut


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    path: str | None = None


class UpdateProjectResponse(BaseModel):
    project: ProjectOut


class DeleteProjectResponse(BaseModel):
    deletedProjectId: str


class ReorderProjectsRequest(BaseModel):
    projectIds: list[str]


class CreateChatRequest(BaseModel):
    title: str


class CreateChatResponse(BaseModel):
    chat: ProjectChatOut


class UpdateChatRequest(BaseModel):
    title: str | None = None
    isPinned: bool | None = None


class UpdateChatResponse(BaseModel):
    chat: ProjectChatOut


class DeleteChatResponse(BaseModel):
    deletedChatId: str
    fallbackChatId: str | None = None


class ReorderChatsRequest(BaseModel):
    chatIds: list[str]
