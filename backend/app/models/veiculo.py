from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Veiculo(Base):
    __tablename__ = "veiculos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    marca: Mapped[str] = mapped_column(String(100), nullable=False)
    modelo: Mapped[str] = mapped_column(String(100), nullable=False)
    versao: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capacidade_bateria_kwh: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    tipo_conector: Mapped[str] = mapped_column(String(50), nullable=False)
    conector_secundario: Mapped[str | None] = mapped_column(String(50), nullable=True)
    principal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    soc_atual: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0"))
    data_criacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    data_atualizacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
