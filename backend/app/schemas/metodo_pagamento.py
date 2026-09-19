from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MetodoPagamentoCreate(BaseModel):
    usuario_id: int | None = None
    tipo: str
    bandeira: str | None = None
    ultimos_4: str | None = None
    token_gateway: str | None = None
    principal: bool = False


class MetodoPagamentoResponse(BaseModel):
    id: int
    usuario_id: int
    tipo: str
    bandeira: str | None = None
    ultimos_4: str | None = None
    principal: bool
    ativo: bool
    data_criacao: datetime

    model_config = ConfigDict(from_attributes=True)
