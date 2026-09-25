from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP


ZERO = Decimal("0")
HUNDRED = Decimal("100")
ECONOMIC_POWER_FACTOR = Decimal("0.50")
INTELLIGENT_MAX_POWER_FACTOR = Decimal("0.80")


@dataclass(frozen=True)
class ChargingEstimate:
    quantity_kwh: Decimal
    available_power_kw: Decimal
    charging_power_kw: Decimal
    estimated_minutes: int
    current_soc_percent: Decimal
    estimated_soc_percent: Decimal
    target_soc_percent: Decimal
    unit_price: Decimal
    energy_cost: Decimal
    service_fee: Decimal
    estimated_cost: Decimal


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_charging_estimate(
    *,
    battery_capacity_kwh: Decimal,
    current_soc_percent: Decimal,
    target_soc_percent: Decimal,
    available_power_kw: Decimal,
    available_minutes: int,
    mode: str,
    unit_price: Decimal,
    service_fee: Decimal,
) -> ChargingEstimate:
    if battery_capacity_kwh <= ZERO:
        raise ValueError("A capacidade da bateria deve ser maior que zero.")
    if not ZERO <= current_soc_percent < HUNDRED:
        raise ValueError("O SoC atual deve estar entre 0 e 100.")
    if not current_soc_percent < target_soc_percent <= HUNDRED:
        raise ValueError("A meta de bateria deve ser maior que o SoC atual e no máximo 100%.")
    if available_power_kw <= ZERO:
        raise ValueError("Não há potência disponível para recarga neste posto.")
    if available_minutes <= 0:
        raise ValueError("O tempo disponível deve ser maior que zero.")
    if unit_price < ZERO or service_fee < ZERO:
        raise ValueError("Preço e taxa não podem ser negativos.")
    mode_key = mode.strip().upper()
    if mode_key not in {"RAPIDO", "ECONOMICO", "INTELIGENTE"}:
        raise ValueError("O modo deve ser RAPIDO, ECONOMICO ou INTELIGENTE.")

    energy_to_target = battery_capacity_kwh * (target_soc_percent - current_soc_percent) / HUNDRED
    if mode_key == "RAPIDO":
        charging_power_kw = available_power_kw
    elif mode_key == "ECONOMICO":
        charging_power_kw = available_power_kw * ECONOMIC_POWER_FACTOR
    else:
        target_power_kw = energy_to_target * Decimal("60") / Decimal(available_minutes)
        intelligent_power_limit = available_power_kw * INTELLIGENT_MAX_POWER_FACTOR
        charging_power_kw = min(intelligent_power_limit, target_power_kw)

    energy_within_time = charging_power_kw * Decimal(available_minutes) / Decimal("60")
    quantity_kwh = min(energy_to_target, energy_within_time).quantize(
        Decimal("0.01"), rounding=ROUND_DOWN
    )
    if quantity_kwh <= ZERO:
        raise ValueError("A janela disponível é curta demais para uma recarga mensurável.")
    estimated_minutes = int(
        (quantity_kwh / charging_power_kw * Decimal("60")).to_integral_value(
            rounding=ROUND_CEILING
        )
    )
    estimated_soc = current_soc_percent + quantity_kwh / battery_capacity_kwh * HUNDRED
    energy_cost = _money(quantity_kwh * unit_price)
    service_fee = _money(service_fee)
    estimated_cost = energy_cost + service_fee

    return ChargingEstimate(
        quantity_kwh=quantity_kwh,
        available_power_kw=available_power_kw.quantize(Decimal("0.01")),
        charging_power_kw=charging_power_kw.quantize(Decimal("0.01"), rounding=ROUND_DOWN),
        estimated_minutes=estimated_minutes,
        current_soc_percent=current_soc_percent.quantize(Decimal("0.01")),
        estimated_soc_percent=estimated_soc.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        target_soc_percent=target_soc_percent.quantize(Decimal("0.01")),
        unit_price=_money(unit_price),
        energy_cost=energy_cost,
        service_fee=service_fee,
        estimated_cost=estimated_cost,
    )
