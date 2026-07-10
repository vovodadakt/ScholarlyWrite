import json as _json
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


def gen_uuid():
    return uuid.uuid4().hex


class JsonText(TypeDecorator):
    """JSON stored as TEXT for MySQL < 5.7 compatibility."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return "{}"
        return _json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if not value:
            return {}
        return _json.loads(value)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
