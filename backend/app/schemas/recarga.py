from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EstimativaRecargaRequest(BaseModel):
    estacao_id: int
    conector_id: int
    veiculo_id: int
    modo: Literal["RAPIDO", "ECONOMICO", "INTELIGENTE"] = "INTELIGENTE"
    percentual_desejado: Decimal = Field(default=Decimal("80"), gt=0, le=100)
    tempo_disponivel_minutos: int = Field(default=45, ge=10, le=360)
    model_config = ConfigDict(extra="forbid")


class EstimativaRecargaResponse(BaseModel):
    modo: str
    preco_kwh: Decimal
    quantidade_kwh: Decimal
    tempo_estimado_minutos: int
    tempo_disponivel_minutos: int
    potencia_disponivel_kw: Decimal
    potencia_alocada_kw: Decimal
    soc_atual: Decimal
    soc_estimado: Decimal
    percentual_desejado: Decimal
    valor_energia: Decimal
    taxa_servico: Decimal
    valor_estimado: Decimal


class RecargaCreate(BaseModel):
    veiculo_id: int
    estacao_id: int
    conector_id: int
    modo: Literal["RAPIDO", "ECONOMICO", "INTELIGENTE"] = "INTELIGENTE"
    percentual_desejado: Decimal = Field(default=Decimal("80"), gt=0, le=100)
    tempo_disponivel_minutos: int = Field(default=45, ge=10, le=360)
    model_config = ConfigDict(extra="forbid")


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
    preco_kwh: Decimal | None = None
    taxa_servico: Decimal | None = None
    valor_estimado: Decimal | None = None
    valor_final: Decimal | None = None
    energia_entregue_kwh: Decimal | None = None
    potencia_atual_kw: Decimal | None = None
    tempo_restante_minutos: int | None = None
    agendada_para: datetime | None = None
    iniciada_em: datetime | None = None
    finalizada_em: datetime | None = None
    data_criacao: datetime

    estacao_nome: str | None = None
    estacao_endereco: str | None = None
    veiculo_modelo: str | None = None
    conector_tipo: str | None = None
    conector_potencia_kw: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)


class ResumoRecargasResponse(BaseModel):
    total_recargas: int = 0
    total_kwh: Decimal = Decimal("0")
    total_gasto: Decimal = Decimal("0")
    recarga_ativa: RecargaResponse | None = None

class ConcluirRecargaSimuladaRequest(BaseModel):
    energia_entregue_kwh: Decimal
    soc_final: Decimal
    valor_final: Decimal
    status: str