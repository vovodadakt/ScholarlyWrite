from __future__ import annotations
from pydantic import BaseModel


class ChapterGenerate(BaseModel):
    chapter_title: str
    chapter_context: str = ""
    provider: str | None = None


class ChapterRewrite(BaseModel):
    instruction: str
    provider: str | None = None


class ChapterSave(BaseModel):
    content: str


class ChapterResponse(BaseModel):
    id: str
    title: str
    content: str
    chapter_order: int
    status: str

    model_config = {"from_attributes": True}
