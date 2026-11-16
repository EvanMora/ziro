"""Pantalla para crear una cuenta (/registro), con el mismo diseño del login (spec
2026-11-16-crear-cuenta-design.md, sección 1)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.sin_plantilla

client = TestClient(app)


def test_registro_renderiza():
    r = client.get("/registro")

    assert r.status_code == 200
    html = r.text
    assert "Crea tu cuenta" in html
    assert 'action="/api/v1/auth/registro"' in html
    assert '<label class="float-field__label" for="nombre">Nombre</label>' in html
    assert 'autocomplete="name"' in html
    assert 'autocomplete="email"' in html
    assert 'autocomplete="new-password"' in html
    assert 'maxlength="100"' in html and 'minlength="8"' in html and 'maxlength="128"' in html
    assert "Mínimo 8 caracteres." in html
    assert 'role="alert"' in html
    assert html.count('href="/login"') >= 2  # en el encabezado y en el pie de la tarjeta
    assert "¿Ya tienes cuenta?" in html


def test_registro_usa_el_mismo_diseno_del_login():
    registro, login = client.get("/registro").text, client.get("/login").text

    for comun in ('data-preview-stage', 'class="login-hero"', 'data-login-card', "login.css", "login-card.js",
                  "login-preview.js", "acceso-form.js"):
        assert comun in registro, comun
        assert comun in login, comun
    assert "registro.js" in registro and "login.js" not in registro
    assert "login.js" in login and "registro.js" not in login


def test_registro_con_sesion_va_al_resumen():
    cliente = TestClient(app)
    cliente.post("/api/v1/auth/registro", json={"nombre": "Ana", "email": "ana@x.com", "password": "secreta123"})

    r = cliente.get("/registro", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/resumen"


def test_login_sin_olvidaste_tu_contrasena():
    html = client.get("/login").text

    assert "/recuperar-contrasena" not in html
    assert "Olvidaste" not in html
    assert 'href="/registro"' in html
    assert 'name="recordar"' in html


@pytest.mark.parametrize("ruta", ["/static/js/registro.js", "/static/js/acceso-form.js", "/static/js/login.js"])
def test_estaticos_del_acceso(ruta):
    assert client.get(ruta).status_code == 200


def test_flujo_completo_de_registro():
    cliente = TestClient(app)
    r = cliente.post("/api/v1/auth/registro",
                     json={"nombre": "Ana Gómez", "email": "ana@x.com", "password": "secreta123"})
    assert r.status_code == 201

    resumen = cliente.get("/resumen")
    assert resumen.status_code == 200
    assert "Ana Gómez" in resumen.text
