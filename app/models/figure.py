from sqlalchemy import Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, gen_uuid


class Figure(Base, TimestampMixin):
    __tablename__ = "figures"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("projects.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    caption: Mapped[str] = mapped_column(Text, default="")
    alt_text: Mapped[str] = mapped_column(Text, default="")
    figure_number: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[str] = mapped_column(String(20), default="0.8")  # textwidth fraction
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)  # relative to static/

    project = relationship("Project", backref="figures")
