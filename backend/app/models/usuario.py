from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    nome: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        unique=True,
    )

    senha_hash: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    telefone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    url_foto: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    data_criacao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )