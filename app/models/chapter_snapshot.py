from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, gen_uuid


class ChapterSnapshot(Base, TimestampMixin):
    __tablename__ = "chapter_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    chapter_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("chapters.id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(default=1)
