"""«Hoy» es el día en Colombia, no el del servidor (Vercel corre en UTC: de 7 p. m. a medianoche ya
sería mañana y la app rechazaría la fecha de hoy o guardaría cuentas y metas con la de mañana)."""
from datetime import date, datetime, timezone

from app.services import movimientos


def _servidor_en(monkeypatch, ahora_utc: datetime):
    monkeypatch.setattr(movimientos, "_ahora_utc", lambda: ahora_utc)


def test_de_noche_en_colombia_sigue_siendo_hoy_aunque_en_utc_ya_sea_manana(monkeypatch):
    # 16 nov, 9:30 p. m. en Bogotá = 17 nov, 2:30 a. m. UTC
    _servidor_en(monkeypatch, datetime(2026, 11, 17, 2, 30, tzinfo=timezone.utc))
    assert movimientos.hoy() == date(2026, 11, 16)


def test_a_medianoche_en_colombia_ya_es_el_dia_siguiente(monkeypatch):
    # 17 nov, 12:00 a. m. en Bogotá = 17 nov, 5:00 a. m. UTC
    _servidor_en(monkeypatch, datetime(2026, 11, 17, 5, 0, tzinfo=timezone.utc))
    assert movimientos.hoy() == date(2026, 11, 17)


def test_un_minuto_antes_de_medianoche_en_colombia_sigue_siendo_el_dia(monkeypatch):
    _servidor_en(monkeypatch, datetime(2026, 11, 17, 4, 59, tzinfo=timezone.utc))
    assert movimientos.hoy() == date(2026, 11, 16)
