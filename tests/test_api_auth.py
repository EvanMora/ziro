"""API JSON de auth: login con correo y contraseña y cierre de sesión."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import usuarios

client = TestClient(app)


@pytest.fixture(autouse=True)
def _almacen_de_usuarios_limpio():
    """Cada test arranca sin usuarios guardados (el almacén en memoria se vacía)."""
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


def test_logout_invalida_la_sesion():
    _crear_usuario()
    r = client.post("/api/v1/auth/login", json={"email": "evan@ziro.com", "password": "secreta123"})
    assert r.status_code == 200

    cierre = client.post("/api/v1/auth/logout")

    assert cierre.status_code == 200
    # La cookie de sesión se borra (expira).
    assert "expires=Thu, 01 Jan 1970" in cierre.headers["set-cookie"]
