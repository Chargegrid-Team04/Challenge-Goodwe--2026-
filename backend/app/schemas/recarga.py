from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class EstimativaRecargaRequest(BaseModel):
    estacao_id: int
    conector_id: int
    veiculo_id: int
    modo: str = "ECONOMICO"
    quantidade_kwh: Decimal | None = None
    percentual_desejado: Decimal | None = None
    soc_inicial: Decimal | None = None


class EstimativaRecargaResponse(BaseModel):
    modo: str
    preco_kwh: Decimal
    quantidade_kwh: Decimal
    tempo_estimado_minutos: int
    taxa_servico: Decimal
    valor_estimado: Decimal


class RecargaCreate(BaseModel):
    usuario_id: int | None = None
    veiculo_id: int
    estacao_id: int
    conector_id: int
    modo: str = "ECONOMICO"
    quantidade_kwh: Decimal | None = None
    percentual_desejado: Decimal | None = None
    tempo_disponivel_minutos: int | None = None
    soc_inicial: Decimal | None = None


class RecargaResponse(BaseModel):
    id: int
    usuario_id: int
    veiculo_id: int
    estacao_id: int
    conector_id: int
    modo: str
    status: str
    quantidade_kwh: Decimal | None = None
    percentual_desejado: Decimal | None = None
    tempo_disponivel_minutos: int | None = None
    soc_inicial: Decimal | None = None
    soc_atual: Decimal | None = None
    soc_final: Decimal | None = None
    preco_kwh: Decimal
    taxa_servico: Decimal
    valor_estimado: Decimal | None = None
    valor_final: Decimal | None = None
    energia_entregue_kwh: Decimal
    potencia_atual_kw: Decimal | None = None
    tempo_restante_minutos: int | None = None
    agendada_para: datetime | None = None
    iniciada_em: datetime | None = None
    finalizada_em: datetime | None = None
    data_criacao: datetime

    model_config = ConfigDict(from_attributes=True)


class ResumoRecargasResponse(BaseModel):
    total_recargas: int
    total_kwh: Decimal
    total_gasto: Decimal
    recarga_ativa: RecargaResponse | None = None
