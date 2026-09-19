from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class VeiculoBase(BaseModel):
    marca: str
    modelo: str
    versao: str | None = None
    capacidade_bateria_kwh: Decimal
    tipo_conector: str
    conector_secundario: str | None = None
    principal: bool = False


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


class VeiculoResponse(VeiculoBase):
    id: int
    usuario_id: int
    ativo: bool
    data_criacao: datetime

    model_config = ConfigDict(from_attributes=True)
