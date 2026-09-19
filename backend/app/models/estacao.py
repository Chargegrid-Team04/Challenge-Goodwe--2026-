from datetime import datetime, time
from decimal import Decimal
from typing import List

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Estacao(Base):
    __tablename__ = "estacoes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    endereco: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    url_imagem: Mapped[str | None] = mapped_column(Text, nullable=True)
    avaliacao: Mapped[Decimal | None] = mapped_column(Numeric(2, 1), nullable=True)
    preco_base_kwh: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    preco_rapido_kwh: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    preco_economico_kwh: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    preco_inteligente_kwh: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    horario_pico_inicio: Mapped[time | None] = mapped_column(Time, nullable=True)
    horario_pico_fim: Mapped[time | None] = mapped_column(Time, nullable=True)
    horario_economico_inicio: Mapped[time | None] = mapped_column(Time, nullable=True)
    horario_economico_fim: Mapped[time | None] = mapped_column(Time, nullable=True)
    taxa_ociosidade_minuto: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    tolerancia_ociosidade_minutos: Mapped[int] = mapped_column(Integer, default=0)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    data_criacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    data_atualizacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    conectores: Mapped[List["Conector"]] = relationship("Conector", back_populates="estacao", cascade="all, delete-orphan", lazy="selectin")
