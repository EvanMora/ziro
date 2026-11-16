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


# El usuario con el que entran los tests, como hace /api/v1/auth/login. Mismo nombre que mostraba
# la app cuando el usuario estaba fijo, para que las aserciones sobre el margen sigan valiendo.
USUARIO_PRUEBA = {"email": "evanpro@ziro.com", "password": "secreta123", "nombre": "Evan Pro"}


@pytest.fixture(autouse=True)
def _sesion_real(request, monkeypatch, _almacen_de_movimientos_limpio, _base_de_datos_de_usuarios_en_memoria):
    """Entra con la sesión del usuario demo (id 1): las páginas y las APIs que requieren sesión
    responden para él, como hace el navegador tras el login. Los módulos sin `client` (tests de
    servicio) no necesitan sesión. Los tests de test_sesion.py crean su propio TestClient para
    probar los caminos sin sesión."""
    from app.services import usuarios

    monkeypatch.setattr(usuarios, "RONDAS_BCRYPT", 4)  # bcrypt rápido en tests
    client = getattr(request.module, "client", None)
    if client is None:
        yield
        return
    usuarios.crear(email=USUARIO_PRUEBA["email"], password=USUARIO_PRUEBA["password"], nombre=USUARIO_PRUEBA["nombre"])
    client.post("/api/v1/auth/login", json={"email": USUARIO_PRUEBA["email"], "password": USUARIO_PRUEBA["password"]})
    yield
