from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Recarga(Base):
    __tablename__ = "recargas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    veiculo_id: Mapped[int] = mapped_column(ForeignKey("veiculos.id", ondelete="RESTRICT"), nullable=False)
    estacao_id: Mapped[int] = mapped_column(ForeignKey("estacoes.id", ondelete="RESTRICT"), nullable=False)
    conector_id: Mapped[int] = mapped_column(ForeignKey("conectores.id", ondelete="RESTRICT"), nullable=False)

    modo: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDENTE", nullable=False)

    quantidade_kwh: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    percentual_desejado: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    tempo_disponivel_minutos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    horario_saida: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    soc_inicial: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    soc_atual: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    soc_final: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    preco_kwh: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    taxa_servico: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    valor_estimado: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    valor_final: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    energia_entregue_kwh: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0.000"), nullable=False)
    potencia_atual_kw: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    tempo_restante_minutos: Mapped[int | None] = mapped_column(Integer, nullable=True)

    agendada_para: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    iniciada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalizada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    data_criacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    data_atualizacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    veiculo = relationship("Veiculo", lazy="joined")
    estacao = relationship("Estacao", lazy="joined")
    conector = relationship("Conector", lazy="joined")
