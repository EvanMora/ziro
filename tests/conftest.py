import os

# Antes de importar la app: con una clave fija no avisa que falta, y las cookies firmadas en los
# tests (tests/test_sesion.py) usan la misma.
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-" + "x" * 32)
# La base de los tests es siempre una en memoria, elegida ANTES de importar la app: si se eligiera en
# un fixture, los fixtures que corren antes (p. ej. el que vacía los movimientos) borrarían la base
# real data/usuarios.sqlite. Pisa cualquier DATABASE_PATH del entorno o del .env.
os.environ["DATABASE_PATH"] = "sqlite:///:memory:"

import pytest  # noqa: E402

from app.services import categorias, cuentas, database, ia, limites, movimientos, presupuestos
from app.main import app
from app.web.sesion import usuario_actual
from tests import plantilla


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


@pytest.fixture(autouse=True)
def _usuario_de_prueba(request, monkeypatch, _base_de_datos_de_usuarios_en_memoria):
    """El usuario 1 con la plantilla de datos (tests/plantilla.py), salvo en los tests marcados
    sin_plantilla, que prueban el registro, el login o la protección reales."""
    if request.node.get_closest_marker("sin_plantilla"):
        yield
        return
    plantilla.crear_usuario()
    plantilla.instalar(monkeypatch)
    # La sesión simulada: las páginas y la API ven al usuario de prueba sin pasar por el login.
    app.dependency_overrides[usuario_actual] = lambda: plantilla.USUARIO_PRUEBA
    yield
    app.dependency_overrides.pop(usuario_actual, None)


@pytest.fixture(autouse=True)
def _limites_de_intentos_limpios():
    """Cada test arranca sin intentos de login ni de registro contados."""
    limites.reiniciar_todos()
    yield
    limites.reiniciar_todos()


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "sin_plantilla: el test no usa el usuario de prueba con la plantilla de datos ni la sesión "
        "simulada (prueba el login, el registro o la protección reales).",
    )
