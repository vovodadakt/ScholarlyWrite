from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JsonText, TimestampMixin, gen_uuid


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="draft")
    context: Mapped[dict] = mapped_column(JsonText, default=dict)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    deadline: Mapped[str] = mapped_column(String(30), nullable=True)
    tags: Mapped[list] = mapped_column(JsonText, default=list)
    template_name: Mapped[str] = mapped_column(String(100), default="")
    journal_style: Mapped[str] = mapped_column(String(50), default="")
    conversation_summary: Mapped[str] = mapped_column(Text, default="")

    user = relationship("User", back_populates="projects")
    outlines = relationship("Outline", back_populates="project", cascade="all, delete-orphan")
    chapters = relationship("Chapter", back_populates="project", cascade="all, delete-orphan")
    conversation_messages = relationship(
        "ConversationMessage", back_populates="project", cascade="all, delete-orphan"
    )
