from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP


ZERO = Decimal("0")
ONE = Decimal("1")
MIN_SAFE_POWER_KW = Decimal("1.40")
MAX_SURGE_MULTIPLIER = Decimal("2.00")


@dataclass(frozen=True)
class ChargingLoad:
    charging_id: int
    requested_power_kw: Decimal


@dataclass(frozen=True)
class ChargingAllocation:
    charging_id: int
    requested_power_kw: Decimal
    allocated_power_kw: Decimal
    reduction_percent: Decimal


@dataclass(frozen=True)
class EnergyManagementResult:
    total_requested_power_kw: Decimal
    total_allocated_power_kw: Decimal
    available_power_kw: Decimal
    utilization_percent: Decimal
    price_per_kwh: Decimal
    price_multiplier: Decimal
    peak_period: bool
    allocations: list[ChargingAllocation]


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _percent(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def is_peak_period(current_time: time, peak_start: time | None, peak_end: time | None) -> bool:
    if peak_start is None or peak_end is None:
        return False
    if peak_start <= peak_end:
        return peak_start <= current_time < peak_end
    return current_time >= peak_start or current_time < peak_end


def calculate_energy_management(
    loads: list[ChargingLoad],
    *,
    station_capacity_kw: Decimal,
    base_price_per_kwh: Decimal,
    current_at: datetime,
    peak_start: time | None = None,
    peak_end: time | None = None,
    external_price_multiplier: Decimal = ONE,
    minimum_power_kw: Decimal = MIN_SAFE_POWER_KW,
) -> EnergyManagementResult:
    """Allocate safe charging power and calculate a transparent dynamic price.

    This function is intentionally deterministic. A future AI may explain or forecast
    demand, but safety limits and billing rules remain enforced by application code.
    """
    if station_capacity_kw <= ZERO:
        raise ValueError("station_capacity_kw must be greater than zero")
    if base_price_per_kwh < ZERO:
        raise ValueError("base_price_per_kwh cannot be negative")
    if external_price_multiplier <= ZERO:
        raise ValueError("external_price_multiplier must be greater than zero")
    if minimum_power_kw < ZERO:
        raise ValueError("minimum_power_kw cannot be negative")

    normalized_loads = [
        ChargingLoad(item.charging_id, max(ZERO, Decimal(item.requested_power_kw)))
        for item in loads
    ]
    total_requested = sum((item.requested_power_kw for item in normalized_loads), ZERO)
    available = Decimal(station_capacity_kw)
    peak = is_peak_period(current_at.time(), peak_start, peak_end)

    if total_requested <= available:
        allocations = [
            ChargingAllocation(item.charging_id, item.requested_power_kw, item.requested_power_kw, ZERO)
            for item in normalized_loads
        ]
    else:
        safe_floor_total = minimum_power_kw * Decimal(len(normalized_loads))
        if safe_floor_total > available:
            allocation_factor = available / total_requested
            allocated_values = [item.requested_power_kw * allocation_factor for item in normalized_loads]
        else:
            remaining = available - safe_floor_total
            excess_total = sum(
                (max(ZERO, item.requested_power_kw - minimum_power_kw) for item in normalized_loads),
                ZERO,
            )
            allocated_values = [
                minimum_power_kw
                + (max(ZERO, item.requested_power_kw - minimum_power_kw) / excess_total * remaining)
                if excess_total > ZERO
                else minimum_power_kw
                for item in normalized_loads
            ]

        allocations = []
        for item, allocated in zip(normalized_loads, allocated_values):
            reduction = ZERO if item.requested_power_kw == ZERO else (
                (ONE - allocated / item.requested_power_kw) * Decimal(100)
            )
            allocations.append(
                ChargingAllocation(
                    item.charging_id,
                    item.requested_power_kw,
                    allocated,
                    _percent(max(ZERO, reduction)),
                )
            )

    total_allocated = sum((item.allocated_power_kw for item in allocations), ZERO)
    utilization = (total_allocated / available * Decimal(100)) if available else ZERO
    utilization_factor = min(MAX_SURGE_MULTIPLIER, max(ONE, total_requested / available))
    peak_factor = Decimal("1.25") if peak else ONE
    price_multiplier = min(MAX_SURGE_MULTIPLIER, utilization_factor * peak_factor * external_price_multiplier)

    return EnergyManagementResult(
        total_requested_power_kw=total_requested,
        total_allocated_power_kw=total_allocated,
        available_power_kw=available,
        utilization_percent=_percent(utilization),
        price_per_kwh=_money(Decimal(base_price_per_kwh) * price_multiplier),
        price_multiplier=_percent(price_multiplier),
        peak_period=peak,
        allocations=allocations,
    )
