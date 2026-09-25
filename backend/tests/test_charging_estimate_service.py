from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.recarga import EstimativaRecargaRequest, RecargaCreate
from app.services.charging_estimate_service import calculate_charging_estimate


def test_estimate_caps_energy_by_available_station_power_and_time():
    result = calculate_charging_estimate(
        battery_capacity_kwh=Decimal("60"),
        current_soc_percent=Decimal("50"),
        target_soc_percent=Decimal("80"),
        available_power_kw=Decimal("14"),
        available_minutes=45,
        mode="RAPIDO",
        unit_price=Decimal("1.89"),
        service_fee=Decimal("2.50"),
    )

    assert result.quantity_kwh == Decimal("10.50")
    assert result.estimated_minutes == 45
    assert result.estimated_soc_percent == Decimal("67.50")
    assert result.energy_cost == Decimal("19.85")
    assert result.estimated_cost == Decimal("22.35")


def test_estimate_stops_at_target_soc_when_time_is_long_enough():
    result = calculate_charging_estimate(
        battery_capacity_kwh=Decimal("60"),
        current_soc_percent=Decimal("50"),
        target_soc_percent=Decimal("80"),
        available_power_kw=Decimal("22"),
        available_minutes=120,
        mode="RAPIDO",
        unit_price=Decimal("1.89"),
        service_fee=Decimal("2.50"),
    )

    assert result.quantity_kwh == Decimal("18.00")
    assert result.estimated_minutes == 50
    assert result.estimated_soc_percent == Decimal("80.00")
    assert result.energy_cost == Decimal("34.02")


def test_rounding_never_exceeds_time_window_and_more_power_adds_energy():
    short_window = calculate_charging_estimate(
        battery_capacity_kwh=Decimal("60"),
        current_soc_percent=Decimal("50"),
        target_soc_percent=Decimal("80"),
        available_power_kw=Decimal("22"),
        available_minutes=10,
        mode="RAPIDO",
        unit_price=Decimal("1.89"),
        service_fee=Decimal("2.50"),
    )
    less_available_power = calculate_charging_estimate(
        battery_capacity_kwh=Decimal("60"),
        current_soc_percent=Decimal("50"),
        target_soc_percent=Decimal("80"),
        available_power_kw=Decimal("14"),
        available_minutes=45,
        mode="RAPIDO",
        unit_price=Decimal("1.89"),
        service_fee=Decimal("2.50"),
    )
    more_available_power = calculate_charging_estimate(
        battery_capacity_kwh=Decimal("60"),
        current_soc_percent=Decimal("50"),
        target_soc_percent=Decimal("80"),
        available_power_kw=Decimal("22"),
        available_minutes=45,
        mode="RAPIDO",
        unit_price=Decimal("1.89"),
        service_fee=Decimal("2.50"),
    )

    assert short_window.quantity_kwh == Decimal("3.66")
    assert short_window.estimated_minutes <= 10
    assert more_available_power.quantity_kwh > less_available_power.quantity_kwh


def test_estimate_rejects_no_available_power_and_target_below_soc():
    with pytest.raises(ValueError, match="potência disponível"):
        calculate_charging_estimate(
            battery_capacity_kwh=Decimal("60"),
            current_soc_percent=Decimal("50"),
            target_soc_percent=Decimal("80"),
            available_power_kw=Decimal("0"),
            available_minutes=45,
            mode="RAPIDO",
            unit_price=Decimal("1.89"),
            service_fee=Decimal("2.50"),
        )

    with pytest.raises(ValueError, match="maior que o SoC atual"):
        calculate_charging_estimate(
            battery_capacity_kwh=Decimal("60"),
            current_soc_percent=Decimal("50"),
            target_soc_percent=Decimal("50"),
            available_power_kw=Decimal("22"),
            available_minutes=45,
            mode="RAPIDO",
            unit_price=Decimal("1.89"),
            service_fee=Decimal("2.50"),
        )


def test_charging_modes_change_allocated_power_and_time():
    common = {
        "battery_capacity_kwh": Decimal("60"),
        "current_soc_percent": Decimal("50"),
        "target_soc_percent": Decimal("80"),
        "available_power_kw": Decimal("22"),
        "available_minutes": 120,
        "unit_price": Decimal("1.89"),
        "service_fee": Decimal("2.50"),
    }
    fast = calculate_charging_estimate(**common, mode="RAPIDO")
    economic = calculate_charging_estimate(**common, mode="ECONOMICO")
    intelligent = calculate_charging_estimate(**common, mode="INTELIGENTE")

    assert fast.charging_power_kw == Decimal("22.00")
    assert fast.estimated_minutes == 50
    assert economic.charging_power_kw == Decimal("11.00")
    assert economic.estimated_minutes == 99
    assert intelligent.charging_power_kw == Decimal("9.00")
    assert intelligent.estimated_minutes == 120
    assert {fast.quantity_kwh, economic.quantity_kwh, intelligent.quantity_kwh} == {Decimal("18.00")}


def test_intelligent_mode_is_slower_than_fast_in_short_window():
    common = {
        "battery_capacity_kwh": Decimal("60"),
        "current_soc_percent": Decimal("50"),
        "target_soc_percent": Decimal("80"),
        "available_power_kw": Decimal("22"),
        "available_minutes": 45,
        "unit_price": Decimal("1.89"),
        "service_fee": Decimal("2.50"),
    }
    fast = calculate_charging_estimate(**common, mode="RAPIDO")
    intelligent = calculate_charging_estimate(**common, mode="INTELIGENTE")

    assert fast.charging_power_kw == Decimal("22.00")
    assert intelligent.charging_power_kw == Decimal("17.60")
    assert fast.quantity_kwh == Decimal("16.50")
    assert intelligent.quantity_kwh == Decimal("13.20")
    assert intelligent.estimated_soc_percent < fast.estimated_soc_percent


def test_estimate_rejects_unknown_mode():
    with pytest.raises(ValueError, match="modo deve ser"):
        calculate_charging_estimate(
            battery_capacity_kwh=Decimal("60"),
            current_soc_percent=Decimal("50"),
            target_soc_percent=Decimal("80"),
            available_power_kw=Decimal("22"),
            available_minutes=45,
            mode="SOLAR",
            unit_price=Decimal("1.89"),
            service_fee=Decimal("2.50"),
        )


@pytest.mark.parametrize("minutes", [9, 361])
def test_api_schemas_reject_time_outside_reccharge_limits(minutes):
    payload = {
        "estacao_id": 1,
        "conector_id": 1,
        "veiculo_id": 1,
        "tempo_disponivel_minutos": minutes,
    }

    with pytest.raises(ValidationError):
        EstimativaRecargaRequest.model_validate(payload)

    with pytest.raises(ValidationError):
        RecargaCreate.model_validate(payload)