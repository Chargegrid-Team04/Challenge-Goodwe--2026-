from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP


ZERO = Decimal("0")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class ChargingSourceProfile:
    name: str
    power_factor: Decimal
    price_factor: Decimal
    explanation: str


@dataclass(frozen=True)
class ChargingPrediction:
    source: str
    suggestion: str
    energy_required_kwh: Decimal
    charging_power_kw: Decimal
    estimated_minutes: int
    price_per_kwh: Decimal
    estimated_cost: Decimal
    peak_period: bool
    active_cars: int
    source_is_estimated: bool


SOURCE_PROFILES = {
    "POSTO": ChargingSourceProfile(
        "POSTO", Decimal("1.00"), Decimal("1.00"), "uso prioritário da rede elétrica do posto"
    ),
    "SOLAR": ChargingSourceProfile(
        "SOLAR", Decimal("0.70"), Decimal("0.85"), "uso prioritário da geração solar disponível"
    ),
    "HIBRIDO": ChargingSourceProfile(
        "HIBRIDO", Decimal("0.85"), Decimal("0.95"), "combinação entre geração solar e rede elétrica"
    ),
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def is_peak_hour(current_at: datetime, start: time = time(10, 0), end: time = time(16, 0)) -> bool:
    return start <= current_at.time() < end


def predict_charging(
    *,
    battery_capacity_kwh: Decimal,
    current_soc_percent: Decimal,
    target_soc_percent: Decimal,
    requested_source: str,
    connector_power_kw: Decimal,
    station_capacity_kw: Decimal,
    base_price_per_kwh: Decimal,
    active_cars: int,
    current_at: datetime,
    solar_available_kw: Decimal | None = None,
) -> ChargingPrediction:
    """Estimate charging using explicit rules; no AI is allowed to override safety limits."""
    source_key = requested_source.strip().upper()
    if source_key not in SOURCE_PROFILES:
        raise ValueError("requested_source must be POSTO, SOLAR, or HIBRIDO")
    if battery_capacity_kwh <= ZERO:
        raise ValueError("battery_capacity_kwh must be greater than zero")
    if connector_power_kw <= ZERO or station_capacity_kw <= ZERO:
        raise ValueError("charging power and station capacity must be greater than zero")
    if not ZERO <= current_soc_percent <= HUNDRED:
        raise ValueError("current_soc_percent must be between 0 and 100")
    if not ZERO < target_soc_percent <= HUNDRED:
        raise ValueError("target_soc_percent must be between 0 and 100")
    if target_soc_percent <= current_soc_percent:
        raise ValueError("target_soc_percent must be greater than current_soc_percent")
    if active_cars < 0:
        raise ValueError("active_cars cannot be negative")

    profile = SOURCE_PROFILES[source_key]
    energy_required = battery_capacity_kwh * (target_soc_percent - current_soc_percent) / HUNDRED
    peak = is_peak_hour(current_at)
    shared_capacity = station_capacity_kw / Decimal(active_cars + 1)
    source_power = connector_power_kw * profile.power_factor

    if source_key == "SOLAR" and solar_available_kw is not None:
        source_power = min(source_power, max(ZERO, solar_available_kw))
    elif source_key == "HIBRIDO" and solar_available_kw is not None:
        source_power = min(connector_power_kw, max(ZERO, solar_available_kw + station_capacity_kw * Decimal("0.30")))

    allocated_power = min(connector_power_kw, source_power, shared_capacity)
    if allocated_power <= ZERO:
        raise ValueError("no safe charging power is available for this request")

    estimated_minutes = max(1, int((energy_required / allocated_power * Decimal(60)).to_integral_value(rounding=ROUND_HALF_UP)))
    peak_factor = Decimal("1.25") if peak else Decimal("1.00")
    occupancy_factor = min(Decimal("1.50"), Decimal("1.00") + Decimal(active_cars) * Decimal("0.05"))
    price_per_kwh = _money(Decimal(base_price_per_kwh) * profile.price_factor * peak_factor * occupancy_factor)

    source_estimated = solar_available_kw is None and source_key in {"SOLAR", "HIBRIDO"}
    suggestion = (
        f"Sugestão: usar {profile.name.lower()} ({profile.explanation}). "
        f"Há {active_cars} carro(s) carregando; a potência foi limitada a {allocated_power} kW "
        "para respeitar a capacidade compartilhada da estação."
    )
    if peak:
        suggestion += " O horário atual está no pico (10:00-16:00), por isso a tarifa foi ajustada."
    if source_estimated:
        suggestion += " A potência solar é estimada porque a estação não forneceu telemetria solar."

    return ChargingPrediction(
        source=profile.name,
        suggestion=suggestion,
        energy_required_kwh=energy_required.quantize(Decimal("0.01")),
        charging_power_kw=allocated_power.quantize(Decimal("0.01")),
        estimated_minutes=estimated_minutes,
        price_per_kwh=price_per_kwh,
        estimated_cost=_money(energy_required * price_per_kwh),
        peak_period=peak,
        active_cars=active_cars,
        source_is_estimated=source_estimated,
    )
