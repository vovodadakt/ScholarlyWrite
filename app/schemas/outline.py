from __future__ import annotations
from typing import Any

from pydantic import BaseModel


class OutlineGenerate(BaseModel):
    topic: str
    description: str = ""
    provider: str | None = None


class OutlineSave(BaseModel):
    content: dict[str, Any]


class OutlineResponse(BaseModel):
    id: str
    project_id: str
    content: dict[str, Any]

    model_config = {"from_attributes": True}
