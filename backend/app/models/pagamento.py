from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Pagamento(Base):
    __tablename__ = "pagamentos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recarga_id: Mapped[int] = mapped_column(ForeignKey("recargas.id", ondelete="RESTRICT"), nullable=False)
    metodo_pagamento_id: Mapped[int | None] = mapped_column(ForeignKey("metodos_pagamento.id", ondelete="SET NULL"), nullable=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDENTE", nullable=False)
    transacao_gateway: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pago_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_criacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    data_atualizacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    recarga = relationship("Recarga", lazy="joined")
    metodo_pagamento = relationship("MetodoPagamento", lazy="joined")
