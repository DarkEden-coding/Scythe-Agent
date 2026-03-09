from pydantic import BaseModel, Field


class ProjectMemoryOut(BaseModel):
    id: str
    projectId: str
    title: str
    contentMarkdown: str
    createdAt: str
    updatedAt: str


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
    name: str = Field(min_length=1, max_length=200)
    path: str = Field(min_length=1)


class CreateProjectResponse(BaseModel):
    project: ProjectOut


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    path: str | None = None


class UpdateProjectResponse(BaseModel):
    project: ProjectOut


class DeleteProjectResponse(BaseModel):
    deletedProjectId: str


class ReorderProjectsRequest(BaseModel):
    projectIds: list[str]


class CreateChatRequest(BaseModel):
    title: str = "New chat"


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


class GetProjectMemoriesResponse(BaseModel):
    memories: list[ProjectMemoryOut]


class UpsertProjectMemoryRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    contentMarkdown: str = Field(min_length=1, max_length=2000)


class UpsertProjectMemoryResponse(BaseModel):
    memory: ProjectMemoryOut


class DeleteProjectMemoryResponse(BaseModel):
    deletedTitle: str
