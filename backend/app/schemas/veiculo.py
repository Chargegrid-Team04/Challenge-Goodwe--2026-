from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class VeiculoBase(BaseModel):
    marca: str
    modelo: str
    versao: str | None = None
    capacidade_bateria_kwh: Decimal
    tipo_conector: str
    conector_secundario: str | None = None
    principal: bool = False

    soc_atual: Decimal = Field(
        ge=0,
        le=100,
    )


class VeiculoCreate(VeiculoBase):
    usuario_id: int | None = None


class VeiculoUpdate(BaseModel):
    marca: str | None = None
    modelo: str | None = None
    versao: str | None = None
    capacidade_bateria_kwh: Decimal | None = None
    tipo_conector: str | None = None
    conector_secundario: str | None = None
    principal: bool | None = None

    soc_atual: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
    )


class VeiculoResponse(VeiculoBase):
    id: int
    usuario_id: int
    ativo: bool
    data_criacao: datetime

    model_config = ConfigDict(
        from_attributes=True
    )