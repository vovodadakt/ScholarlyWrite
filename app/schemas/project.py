from pydantic import BaseModel


class ProjectCreate(BaseModel):
    title: str
    description: str = ""


class ProjectResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str
    created_at: str

    model_config = {"from_attributes": True}
