from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.charging_prediction_service import predict_charging


def test_hybrid_prediction_calculates_time_cost_and_peak_price():
    result = predict_charging(
        battery_capacity_kwh=Decimal("60"),
        current_soc_percent=Decimal("20"),
        target_soc_percent=Decimal("80"),
        requested_source="HIBRIDO",
        connector_power_kw=Decimal("22"),
        station_capacity_kw=Decimal("44"),
        base_price_per_kwh=Decimal("0.40"),
        active_cars=1,
        current_at=datetime(2026, 9, 22, 11, 0, tzinfo=timezone.utc),
    )

    assert result.energy_required_kwh == Decimal("36.00")
    assert result.charging_power_kw == Decimal("18.70")
    assert result.estimated_minutes > 0
    assert result.peak_period is True
    assert result.price_per_kwh > Decimal("0.40")
    assert result.estimated_cost > Decimal("0")
    assert result.source_is_estimated is True


def test_solar_telemetry_limits_solar_power():
    result = predict_charging(
        battery_capacity_kwh=Decimal("40"),
        current_soc_percent=Decimal("30"),
        target_soc_percent=Decimal("50"),
        requested_source="SOLAR",
        connector_power_kw=Decimal("22"),
        station_capacity_kw=Decimal("50"),
        base_price_per_kwh=Decimal("0.40"),
        active_cars=0,
        current_at=datetime(2026, 9, 22, 9, 0, tzinfo=timezone.utc),
        solar_available_kw=Decimal("8"),
    )

    assert result.charging_power_kw == Decimal("8.00")
    assert result.peak_period is False
    assert result.source_is_estimated is False


def test_invalid_source_is_rejected():
    with pytest.raises(ValueError, match="POSTO, SOLAR, or HIBRIDO"):
        predict_charging(
            battery_capacity_kwh=Decimal("40"),
            current_soc_percent=Decimal("20"),
            target_soc_percent=Decimal("80"),
            requested_source="EOLICA",
            connector_power_kw=Decimal("22"),
            station_capacity_kw=Decimal("50"),
            base_price_per_kwh=Decimal("0.40"),
            active_cars=0,
            current_at=datetime.now(timezone.utc),
        )
