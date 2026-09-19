from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Conector(Base):
    __tablename__ = "conectores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    estacao_id: Mapped[int] = mapped_column(ForeignKey("estacoes.id", ondelete="CASCADE"), nullable=False)
    codigo: Mapped[str] = mapped_column(String(50), nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    potencia_kw: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DISPONIVEL", nullable=False)
    data_criacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    data_atualizacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    estacao: Mapped["Estacao"] = relationship("Estacao", back_populates="conectores")
