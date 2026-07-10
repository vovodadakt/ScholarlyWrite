from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, gen_uuid


class UserSettings(Base, TimestampMixin):
    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=False, unique=True
    )
    ai_provider: Mapped[str] = mapped_column(String(50), default="")
    api_key: Mapped[str] = mapped_column(String(255), default="")
    api_base_url: Mapped[str] = mapped_column(String(500), default="")
    ai_model: Mapped[str] = mapped_column(String(100), default="")
    system_font: Mapped[str] = mapped_column(String(100), default="")
    editor_font: Mapped[str] = mapped_column(String(100), default="")

    user = relationship("User", back_populates="settings")
