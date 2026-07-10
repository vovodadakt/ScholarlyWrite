from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JsonText, TimestampMixin, gen_uuid


class Experiment(Base, TimestampMixin):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("projects.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    objective: Mapped[str] = mapped_column(Text, default="")
    hypothesis: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="planned")
    tags: Mapped[list] = mapped_column(JsonText, default=list)
    steps: Mapped[list] = mapped_column(JsonText, default=list)
    materials: Mapped[list] = mapped_column(JsonText, default=list)
    equipment: Mapped[list] = mapped_column(JsonText, default=list)
    conditions: Mapped[dict] = mapped_column(JsonText, default=dict)
    images: Mapped[list] = mapped_column(JsonText, default=list)
    results_observations: Mapped[str] = mapped_column(Text, default="")
    conclusion: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)

    project = relationship("Project")
