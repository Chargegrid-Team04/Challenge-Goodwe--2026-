from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ChargingPredictionRequest(BaseModel):
    estacao_id: int
    veiculo_id: int
    requested_source: Literal["POSTO", "SOLAR", "HIBRIDO"] = "HIBRIDO"
    current_soc_percent: Decimal = Field(..., ge=0, le=100)
    target_soc_percent: Decimal = Field(..., gt=0, le=100)
    station_capacity_kw: Decimal = Field(..., gt=0)
    current_at: datetime | None = None
    solar_available_kw: Decimal | None = Field(default=None, ge=0)


class ChargingPredictionResponse(BaseModel):
    estacao_id: int
    veiculo_id: int
    active_cars: int
    source: str
    suggestion: str
    energy_required_kwh: Decimal
    charging_power_kw: Decimal
    estimated_minutes: int
    price_per_kwh: Decimal
    estimated_cost: Decimal
    peak_period: bool
    source_is_estimated: bool
