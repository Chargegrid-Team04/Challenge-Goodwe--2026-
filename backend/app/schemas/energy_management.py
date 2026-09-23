from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class EnergyManagementRequest(BaseModel):
    estacao_id: int
    station_capacity_kw: Decimal = Field(..., gt=0, description="Limite seguro da instalação em kW.")
    current_at: datetime | None = None
    external_price_multiplier: Decimal = Field(default=Decimal("1.00"), gt=0, le=2)
    minimum_power_kw: Decimal = Field(default=Decimal("1.40"), ge=0)
    aplicar_ajuste: bool = Field(
        default=False,
        description="Se verdadeiro, persiste a potência alocada nas recargas ativas.",
    )


class ChargingAllocationResponse(BaseModel):
    recarga_id: int
    requested_power_kw: Decimal
    allocated_power_kw: Decimal
    reduction_percent: Decimal


class EnergyManagementResponse(BaseModel):
    estacao_id: int
    active_charging_count: int
    total_requested_power_kw: Decimal
    total_allocated_power_kw: Decimal
    available_power_kw: Decimal
    utilization_percent: Decimal
    price_per_kwh: Decimal
    price_multiplier: Decimal
    peak_period: bool
    allocations: list[ChargingAllocationResponse]
