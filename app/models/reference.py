from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JsonText, TimestampMixin, gen_uuid


class Reference(Base, TimestampMixin):
    __tablename__ = "references"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[list] = mapped_column(JsonText, default=list)
    year: Mapped[int] = mapped_column(Integer, nullable=True)
    journal: Mapped[str] = mapped_column(String(500), default="")
    doi: Mapped[str] = mapped_column(String(255), default="")
    url: Mapped[str] = mapped_column(String(1000), default="")
    abstract: Mapped[str] = mapped_column(Text, default="")
    citation_key: Mapped[str] = mapped_column(String(200), default="", unique=True)
    pub_type: Mapped[str] = mapped_column(String(30), default="article")
    volume: Mapped[str] = mapped_column(String(100), default="")
    issue: Mapped[str] = mapped_column(String(100), default="")
    pages: Mapped[str] = mapped_column(String(100), default="")
    publisher: Mapped[str] = mapped_column(String(100), default="")
    raw_bibtex: Mapped[str] = mapped_column(Text, default="")

    project = relationship("Project")
