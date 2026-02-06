from pydantic import BaseModel


class FsChildOut(BaseModel):
    name: str
    path: str
    kind: str
    hasChildren: bool


class FsChildrenResponse(BaseModel):
    path: str
    parentPath: str | None
    children: list[FsChildOut]
    allowedRoots: list[str]
