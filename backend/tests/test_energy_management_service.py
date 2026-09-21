from datetime import datetime, time, timezone
from decimal import Decimal

import pytest

from app.services.energy_management_service import ChargingLoad, calculate_energy_management


def test_reduces_load_when_requested_power_exceeds_station_capacity():
    result = calculate_energy_management(
        [
            ChargingLoad(1, Decimal("22")),
            ChargingLoad(2, Decimal("22")),
        ],
        station_capacity_kw=Decimal("30"),
        base_price_per_kwh=Decimal("0.40"),
        current_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
    )

    assert result.total_requested_power_kw == Decimal("44")
    assert result.total_allocated_power_kw <= Decimal("30")
    assert all(item.allocated_power_kw < item.requested_power_kw for item in result.allocations)
    assert all(item.reduction_percent > 0 for item in result.allocations)


def test_peak_period_and_demand_increase_price():
    result = calculate_energy_management(
        [ChargingLoad(1, Decimal("20"))],
        station_capacity_kw=Decimal("20"),
        base_price_per_kwh=Decimal("0.40"),
        current_at=datetime(2026, 9, 20, 18, 30, tzinfo=timezone.utc),
        peak_start=time(18, 0),
        peak_end=time(21, 0),
    )

    assert result.peak_period is True
    assert result.price_per_kwh == Decimal("0.50")
    assert result.price_multiplier == Decimal("1.25")


def test_invalid_capacity_is_rejected():
    with pytest.raises(ValueError):
        calculate_energy_management(
            [],
            station_capacity_kw=Decimal("0"),
            base_price_per_kwh=Decimal("0.40"),
            current_at=datetime.now(timezone.utc),
        )
