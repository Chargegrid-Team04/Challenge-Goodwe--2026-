from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class PagamentoCreate(BaseModel):
    recarga_id: int
    metodo_pagamento_id: int | None = None
    valor: Decimal | None = None


class PagamentoResponse(BaseModel):
    id: int
    recarga_id: int
    metodo_pagamento_id: int | None = None
    valor: Decimal
    status: str
    transacao_gateway: str | None = None
    pago_em: datetime | None = None
    data_criacao: datetime

    model_config = ConfigDict(from_attributes=True)
