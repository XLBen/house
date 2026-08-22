from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Meta(Base):
    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
