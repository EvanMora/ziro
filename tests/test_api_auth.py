"""API JSON de auth: login con correo y contraseña y cierre de sesión."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import limites, usuarios

pytestmark = pytest.mark.sin_plantilla

client = TestClient(app)


@pytest.fixture(autouse=True)
def _almacen_de_usuarios_limpio():
    """Cada test arranca sin usuarios guardados (la base de datos se vacía)."""
    usuarios.reiniciar()
    yield
    usuarios.reiniciar()


def _crear_usuario(email: str = "evan@ziro.com", password: str = "secreta123", nombre: str = "Evan Pro"):
    return usuarios.crear(email=email, password=password, nombre=nombre)


def test_login_con_credenciales_validas_devuelve_al_usuario_y_sesion():
    _crear_usuario()
    r = client.post("/api/v1/auth/login", json={"email": "evan@ziro.com", "password": "secreta123"})

    assert r.status_code == 200
    assert r.json()["id"] == 1
    assert r.json()["nombre"] == "Evan Pro"
    assert r.json()["correo"] == "evan@ziro.com"
    assert r.json()["iniciales"] == "EP"
    # La sesión se escribió en la cookie (la que firma el SessionMiddleware con SECRET_KEY).
    assert "session=" in r.headers["set-cookie"]


def test_login_contrasena_incorrecta_responde_401():
    _crear_usuario()
    r = client.post("/api/v1/auth/login", json={"email": "evan@ziro.com", "password": "otra-cosa"})

    assert r.status_code == 401
    assert r.json()["detail"]


def test_login_de_usuario_inexistente_responde_401():
    r = client.post("/api/v1/auth/login", json={"email": "nadie@ziro.com", "password": "secreta123"})

    assert r.status_code == 401


def test_login_con_campo_faltante_responde_422():
    r = client.post("/api/v1/auth/login", json={"email": "evan@ziro.com"})

    assert r.status_code == 422


def test_registro_crea_usuario_en_la_base_de_datos():
    r = client.post(
        "/api/v1/auth/registro",
        json={"nombre": "Nuevo Usuario", "email": "nuevo@ziro.com", "password": "secreta123"},
    )

    assert r.status_code == 201
    assert r.json()["id"] == 1
    assert r.json()["nombre"] == "Nuevo Usuario"
    assert r.json()["correo"] == "nuevo@ziro.com"
    # El usuario quedó guardado en la base de datos de usuarios (SQLite vía SQLAlchemy).
    assert usuarios.obtener(1) is not None
    assert usuarios.obtener(1).email == "nuevo@ziro.com"


def test_registro_con_correo_duplicado_responde_error_de_validacion():
    _crear_usuario()
    r = client.post(
        "/api/v1/auth/registro",
        json={"nombre": "Evan Pro", "email": "evan@ziro.com", "password": "secreta123"},
    )

    assert r.status_code == 422
    assert "email" in r.json()["errores"]


def test_registro_con_campos_faltantes_responde_422():
    r = client.post("/api/v1/auth/registro", json={"email": "sin-password@ziro.com"})

    assert r.status_code == 422


def test_registro_y_luego_login_guardan_sesion():
    r = client.post(
        "/api/v1/auth/registro",
        json={"nombre": "Nuevo Usuario", "email": "nuevo@ziro.com", "password": "secreta123"},
    )
    assert r.status_code == 201

    login = client.post("/api/v1/auth/login", json={"email": "nuevo@ziro.com", "password": "secreta123"})

    assert login.status_code == 200


def test_logout_invalida_la_sesion():
    _crear_usuario()
    r = client.post("/api/v1/auth/login", json={"email": "evan@ziro.com", "password": "secreta123"})
    assert r.status_code == 200

    cierre = client.post("/api/v1/auth/logout")

    assert cierre.status_code == 200
    # La cookie de sesión se borra (expira).
    assert "expires=Thu, 01 Jan 1970" in cierre.headers["set-cookie"]


def _login(cliente, password="secreta123", email="evan@ziro.com"):
    return cliente.post("/api/v1/auth/login", json={"email": email, "password": password})


def _registro(cliente, email, nombre="Nuevo Usuario", password="secreta123"):
    return cliente.post("/api/v1/auth/registro", json={"nombre": nombre, "email": email, "password": password})


def test_registro_valida_en_el_servidor():
    r = _registro(client, "nuevo@ziro.com", nombre="  ")
    assert r.status_code == 422
    assert "nombre" in r.json()["errores"]

    r = _registro(client, "nuevo@ziro.com", password="1234567")
    assert r.status_code == 422
    assert "password" in r.json()["errores"]

    r = _registro(client, "no-es-correo")
    assert r.status_code == 422
    assert "email" in r.json()["errores"]


def test_registro_guarda_el_correo_en_minusculas_y_entra_con_mayusculas():
    assert _registro(client, "  Nuevo@Ziro.COM ").json()["correo"] == "nuevo@ziro.com"

    assert _login(client, email="NUEVO@ziro.com").status_code == 200


def test_login_bloquea_al_sexto_fallo():
    _crear_usuario()
    for _ in range(5):
        assert _login(client, password="mala-clave").status_code == 401

    r = _login(client)  # aun con la contraseña correcta
    assert r.status_code == 429
    assert r.json()["detail"] == "Hiciste demasiados intentos. Espera unos minutos antes de volver a intentar."


def test_bloqueo_termina_al_pasar_la_ventana(monkeypatch):
    _crear_usuario()
    for _ in range(5):
        _login(client, password="mala-clave")
    assert _login(client).status_code == 429

    real = limites.ahora()
    monkeypatch.setattr(limites, "ahora", lambda: real + timedelta(minutes=15, seconds=1))
    assert _login(client).status_code == 200


def test_login_correcto_limpia_el_contador_del_correo():
    _crear_usuario()
    cliente_a = TestClient(app, client=("10.0.0.1", 1000))
    cliente_b = TestClient(app, client=("10.0.0.2", 1000))
    for _ in range(4):
        _login(cliente_a, password="mala-clave")
    assert _login(cliente_a).status_code == 200
    for _ in range(4):
        assert _login(cliente_b, password="mala-clave").status_code == 401

    # Sin limpiar, el correo llevaría 8 fallos y estaría bloqueado.
    assert _login(cliente_b).status_code == 200


def test_el_limite_por_ip_cubre_varios_correos():
    for i in range(5):
        _login(client, email=f"nadie{i}@ziro.com")

    assert _login(client, email="otro@ziro.com").status_code == 429


def test_registro_bloquea_al_sexto_intento_por_ip():
    for i in range(5):
        assert _registro(client, f"nuevo{i}@ziro.com").status_code == 201

    assert _registro(client, "nuevo9@ziro.com").status_code == 429


def test_logout_cierra_la_sesion():
    _crear_usuario()
    cliente = TestClient(app)
    _login(cliente)

    assert cliente.post("/api/v1/auth/logout").status_code == 200
    assert "session" not in cliente.cookies
