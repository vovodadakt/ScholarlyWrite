from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JsonText, TimestampMixin, gen_uuid


class Outline(Base, TimestampMixin):
    __tablename__ = "outlines"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.id"), nullable=False, unique=True
    )
    content: Mapped[dict] = mapped_column(JsonText, default=dict)

    project = relationship("Project", back_populates="outlines")
