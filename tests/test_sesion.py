"""La sesión real: sin sesión las páginas van a /login y las APIs responden 401; con sesión, los
datos son solo del usuario que entró (el demo ya no es fijo para todo el mundo)."""
import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.main import app
from app.models.usuarios import UsuarioDB
from app.services import database

client = TestClient(app)  # la usa conftest para entrar con el usuario demo (id 1)


def _anonimo() -> TestClient:
    """Un cliente nuevo: sin cookie de sesión."""
    return TestClient(app)


# ---------- Sin sesión ----------

@pytest.mark.parametrize("ruta", ["/resumen", "/movimientos", "/cuentas", "/categorias",
                                  "/presupuestos", "/presupuestos/nuevo"])
def test_pagina_sin_sesion_va_al_login(ruta):
    r = _anonimo().get(ruta, follow_redirects=False)

    assert r.status_code == 307
    assert r.headers["location"] == "/login"


def test_la_raiz_sin_sesion_va_al_login():
    r = _anonimo().get("/", follow_redirects=False)

    assert r.status_code == 307
    assert r.headers["location"] == "/login"


@pytest.mark.parametrize("url", ["/api/v1/movimientos?anio=2026&mes=11", "/api/v1/cuentas",
                                 "/api/v1/categorias", "/api/v1/presupuestos/2026/11"])
def test_api_sin_sesion_responde_401(url):
    r = _anonimo().get(url)

    assert r.status_code == 401
    assert r.json()["detail"]


def test_api_crear_sin_sesion_responde_401():
    r = _anonimo().post("/api/v1/movimientos", json={})

    assert r.status_code == 401


# ---------- Con sesión ----------

def test_el_resumen_muestra_al_usuario_de_la_sesion_y_su_cierre():
    html = client.get("/resumen").text

    assert html.count('aria-current="page"') == 1
    assert "Evan Pro" in html
    assert "evanpro@ziro.com" in html
    assert "Cerrar sesión" in html


def test_la_raiz_con_sesion_va_al_resumen():
    r = client.get("/", follow_redirects=False)

    assert r.status_code == 307
    assert r.headers["location"] == "/resumen"


def test_cerrar_sesion_borra_la_cookie_y_vuelve_al_login():
    r = client.post("/logout", follow_redirects=False)

    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    assert client.get("/resumen", follow_redirects=False).status_code == 307


def test_la_sesion_sirve_solo_sus_datos():
    """El segundo usuario no ve las cuentas demo: el aislamiento es real, no por defecto."""
    otro = _anonimo()
    r = otro.post("/api/v1/auth/registro", json={"nombre": "Ana Otra", "email": "ana@ziro.com",
                                                 "password": "secreta123"})
    assert r.status_code == 201

    r = otro.get("/api/v1/cuentas")
    assert r.status_code == 200
    assert r.json()["dinero"] == []
    assert r.json()["tienes"] == "0"

    html = otro.get("/resumen").text
    assert "Ana Otra" in html
    assert "Cuenta de ahorros" not in html


# ---------- Contraseñas ----------

def test_la_contrasena_se_guarda_con_bcrypt():
    r = client.post("/api/v1/auth/registro", json={"nombre": "Hash", "email": "hash@ziro.com",
                                                   "password": "secreta123"})

    assert r.status_code == 201
    with database.sesion() as db:
        usuario_db = db.get(UsuarioDB, r.json()["id"])
        assert usuario_db.password_hash.startswith("$2b$")


def test_el_hash_sha256_antiguo_sigue_entrando_y_se_migra_a_bcrypt():
    con_sesion_vieja = _anonimo()
    with database.sesion() as db:
        db.add(UsuarioDB(nombre="Viejo", email="viejo@ziro.com",
                         password_hash=hashlib.sha256("vieja".encode("utf-8")).hexdigest()))
        db.commit()

    r = con_sesion_vieja.post("/api/v1/auth/login", json={"email": "viejo@ziro.com", "password": "vieja"})

    assert r.status_code == 200
    with database.sesion() as db:
        viejo_id = db.execute(
            select(UsuarioDB.id).where(UsuarioDB.email == "viejo@ziro.com")
        ).scalar_one()
        assert db.get(UsuarioDB, viejo_id).password_hash.startswith("$2b$")


def test_sesion_huerfana_vuelve_al_login():
    with database.sesion() as db:
        db.execute(delete(UsuarioDB).where(UsuarioDB.id == 1))
        db.commit()

    r = client.get("/resumen", follow_redirects=False)

    assert r.status_code == 307
    assert r.headers["location"] == "/login"
