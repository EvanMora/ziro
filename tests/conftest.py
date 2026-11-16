import pytest

from app.services import categorias, cuentas, database, ia, movimientos, presupuestos


@pytest.fixture(autouse=True)
def _almacen_de_movimientos_limpio():
    """Cada test arranca con el almacén en memoria vacío (se vuelve a sembrar al pedir un mes) y
    sin categorías propias, sin consultas al asistente contadas para el límite de uso ni análisis
    guardados."""
    movimientos.reiniciar()
    categorias.reiniciar()
    cuentas.reiniciar()
    ia.reiniciar_limite()
    ia.reiniciar_cache_analisis()
    presupuestos.reiniciar()
    yield
    movimientos.reiniciar()
    categorias.reiniciar()
    cuentas.reiniciar()
    ia.reiniciar_limite()
    ia.reiniciar_cache_analisis()
    presupuestos.reiniciar()


@pytest.fixture(autouse=True)
def _base_de_datos_de_usuarios_en_memoria(monkeypatch):
    """Cada test arranca la base de datos de usuarios en memoria (SQLite) y sin usuarios guardados."""
    monkeypatch.setattr(database, "DATABASE_PATH", "sqlite:///:memory:")
    database.reiniciar()
    yield
    database.reiniciar()
