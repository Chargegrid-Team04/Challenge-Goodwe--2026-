from sqlalchemy.exc import SQLAlchemyError

from app.services.ai_service import get_charging_stations_context


class BrokenSession:
    def execute(self, *args, **kwargs):
        raise SQLAlchemyError("table does not exist")


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *args, **kwargs):
        return FakeResult(self.rows)


def test_get_charging_stations_context_returns_fallback_on_database_error():
    context = get_charging_stations_context(BrokenSession())

    assert "GoodWe" in context
    assert "infraestrutura" in context.lower()
    assert "carregadores" in context.lower()


def test_get_charging_stations_context_formats_station_data():
    session = FakeSession([
        {"nome": "Estação Centro", "endereco": "Rua A, 123", "preco_base_kwh": 0.35},
        {"nome": "Estação Norte", "endereco": "Avenida B, 99", "preco_base_kwh": 0.42},
    ])

    context = get_charging_stations_context(session)

    assert "Estação Centro" in context
    assert "Rua A, 123" in context
    assert "0.35" in context
