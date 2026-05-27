from __future__ import annotations
from typing import Optional
from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, gen_uuid


class Chapter(Base, TimestampMixin):
    __tablename__ = "chapters"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    chapter_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="draft")

    parent_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("chapters.id"), nullable=True
    )
    chapter_number: Mapped[str] = mapped_column(String(20), default="")
    level: Mapped[int] = mapped_column(Integer, default=1)

    project = relationship("Project", back_populates="chapters")
    parent = relationship("Chapter", remote_side="Chapter.id", back_populates="children")
    children = relationship("Chapter", back_populates="parent", cascade="all, delete-orphan")
