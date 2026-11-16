"""Cabeceras de seguridad en todas las respuestas y rechazo de peticiones que cambian datos desde otro
sitio (spec 2026-11-16-crear-cuenta-design.md, sección 7)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.sin_plantilla

client = TestClient(app)

CABECERAS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "same-origin",
}


@pytest.mark.parametrize("ruta", ["/login", "/api/v1/categorias", "/static/css/login.css", "/no-existe"])
def test_cabeceras_en_todas_las_respuestas(ruta):
    r = client.get(ruta, follow_redirects=False)

    for nombre, valor in CABECERAS.items():
        assert r.headers.get(nombre) == valor, (ruta, nombre)


@pytest.mark.parametrize("metodo", ["POST", "PUT", "DELETE"])
def test_origen_ajeno_da_403(metodo):
    r = client.request(metodo, "/api/v1/auth/login", headers={"Origin": "https://malo.com"},
                       json={"email": "a@x.com", "password": "x"})

    assert r.status_code == 403
    assert r.json() == {"detail": "Origen no permitido."}


def test_origen_con_otro_puerto_da_403():
    r = client.post("/api/v1/auth/logout", headers={"Origin": "http://testserver:8080"})

    assert r.status_code == 403


def test_origen_propio_pasa():
    r = client.post("/api/v1/auth/login", headers={"Origin": "http://testserver"},
                    json={"email": "a@x.com", "password": "secreta123"})

    assert r.status_code == 401  # credenciales malas, no un rechazo por origen


def test_sin_origin_pasa():
    r = client.post("/api/v1/auth/login", json={"email": "a@x.com", "password": "secreta123"})

    assert r.status_code == 401


def test_get_con_origen_ajeno_no_se_bloquea():
    r = client.get("/login", headers={"Origin": "https://malo.com"})

    assert r.status_code == 200


def test_formulario_fuera_de_la_api_no_se_bloquea():
    # Solo /api/ cambia datos; el resto de rutas son páginas GET.
    r = client.post("/login", headers={"Origin": "https://malo.com"})

    assert r.status_code == 405
