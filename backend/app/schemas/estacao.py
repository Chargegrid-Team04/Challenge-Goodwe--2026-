from datetime import time
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class ConectorResponse(BaseModel):
    id: int
    estacao_id: int
    codigo: str
    tipo: str
    potencia_kw: Decimal
    status: str

    model_config = ConfigDict(from_attributes=True)


class EstacaoResponse(BaseModel):
    id: int
    nome: str
    endereco: str
    latitude: Decimal
    longitude: Decimal
    url_imagem: str | None = None
    avaliacao: Decimal | None = None
    preco_base_kwh: Decimal
    preco_rapido_kwh: Decimal | None = None
    preco_economico_kwh: Decimal | None = None
    preco_inteligente_kwh: Decimal | None = None
    horario_pico_inicio: time | None = None
    horario_pico_fim: time | None = None
    horario_economico_inicio: time | None = None
    horario_economico_fim: time | None = None
    taxa_ociosidade_minuto: Decimal
    tolerancia_ociosidade_minutos: int
    ativa: bool
    distancia_km: float | None = None
    conectores: list[ConectorResponse] = []

    model_config = ConfigDict(from_attributes=True)
