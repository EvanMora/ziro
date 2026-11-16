"""Sin sesión no se ve ni se toca nada: las páginas llevan a /login y la API responde 401. Con sesión,
cada página trabaja con el usuario que entró (spec 2026-11-16-crear-cuenta-design.md, sección 5)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.sin_plantilla

PAGINAS = ["/resumen", "/movimientos", "/cuentas", "/categorias", "/presupuestos", "/presupuestos/nuevo"]

ENDPOINTS = [
    ("GET", "/api/v1/categorias"), ("POST", "/api/v1/categorias"),
    ("PUT", "/api/v1/categorias/1"), ("DELETE", "/api/v1/categorias/1"),
    ("GET", "/api/v1/cuentas"), ("POST", "/api/v1/cuentas"),
    ("PUT", "/api/v1/cuentas/1"), ("DELETE", "/api/v1/cuentas/1"),
    ("POST", "/api/v1/cuentas/1/pagos"), ("PUT", "/api/v1/pagos/1"), ("DELETE", "/api/v1/pagos/1"),
    ("GET", "/api/v1/movimientos"), ("POST", "/api/v1/movimientos"),
    ("PUT", "/api/v1/movimientos/1"), ("DELETE", "/api/v1/movimientos/1"),
    ("GET", "/api/v1/presupuestos/2026/10"), ("PUT", "/api/v1/presupuestos/2026/10"),
    ("POST", "/api/v1/ia/interpretar-movimiento"), ("GET", "/api/v1/ia/analisis-mes"),
    ("GET", "/api/v1/ia/ordenar-otros"), ("POST", "/api/v1/ia/ordenar-otros/aplicar"),
]


def _registrado(nombre="Ana Gómez", correo="ana@x.com") -> TestClient:
    cliente = TestClient(app)
    r = cliente.post("/api/v1/auth/registro", json={"nombre": nombre, "email": correo, "password": "secreta123"})
    assert r.status_code == 201
    return cliente


@pytest.mark.parametrize("pagina", PAGINAS)
def test_paginas_sin_sesion_llevan_al_login(pagina):
    r = TestClient(app).get(pagina, follow_redirects=False)

    assert r.status_code == 303
    assert r.headers["location"] == "/login"


@pytest.mark.parametrize(("metodo", "ruta"), ENDPOINTS)
def test_api_sin_sesion_responde_401(metodo, ruta):
    r = TestClient(app).request(metodo, ruta, json={})

    assert r.status_code == 401
    assert r.json() == {"detail": "Inicia sesión para continuar."}


def test_todas_las_rutas_de_la_api_estan_en_la_lista():
    """Si alguien agrega un endpoint, que también lo agregue aquí (y quede protegido)."""
    publicas = {"/api/v1/auth/registro", "/api/v1/auth/login", "/api/v1/auth/logout"}
    declaradas = {(metodo.upper(), ruta) for ruta, metodos in app.openapi()["paths"].items()
                  if ruta.startswith("/api/") and ruta not in publicas for metodo in metodos}
    concretas = {(m, p.replace("{id}", "1").replace("{anio}", "2026").replace("{mes}", "10")) for m, p in declaradas}
    assert concretas == set(ENDPOINTS)


def test_raiz_sin_sesion_va_al_login():
    r = TestClient(app).get("/", follow_redirects=False)

    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_raiz_con_sesion_va_al_resumen():
    r = _registrado().get("/", follow_redirects=False)

    assert r.status_code == 303
    assert r.headers["location"] == "/resumen"


def test_login_con_sesion_va_al_resumen():
    r = _registrado().get("/login", follow_redirects=False)

    assert r.status_code == 303
    assert r.headers["location"] == "/resumen"


def test_login_sin_sesion_se_ve():
    assert TestClient(app).get("/login").status_code == 200
    assert TestClient(app).get("/static/css/login.css").status_code == 200


@pytest.mark.parametrize("pagina", PAGINAS)
def test_usuario_nuevo_ve_todas_las_paginas(pagina):
    r = _registrado().get(pagina)

    assert r.status_code == 200
    assert "Ana Gómez" in r.text
    assert "ana@x.com" in r.text
    assert "Evan Pro" not in r.text


def test_api_con_sesion_trabaja_con_ese_usuario():
    cliente = _registrado()

    assert cliente.get("/api/v1/cuentas").json()["dinero"] == []
    assert len(cliente.get("/api/v1/categorias").json()) == 7


def test_app_shell_lleva_al_login_si_la_api_responde_401():
    js = (Path(__file__).resolve().parent.parent / "app/static/js/app-shell.js").read_text(encoding="utf-8")

    assert "401" in js
    assert '"/login"' in js


def test_no_queda_usuario_fijo():
    raiz = Path(__file__).resolve().parent.parent
    for carpeta in ("app", "tests"):
        for archivo in (raiz / carpeta).rglob("*.py"):
            if archivo.name in ("test_proteccion.py", "test_sin_demo.py"):
                continue
            assert "USUARIO_DEMO" not in archivo.read_text(encoding="utf-8"), archivo


def test_barra_tiene_cerrar_sesion():
    html = _registrado().get("/resumen").text

    assert "data-logout" in html
    assert "Cerrar sesión" in html


def test_app_shell_cierra_la_sesion():
    js = (Path(__file__).resolve().parent.parent / "app/static/js/app-shell.js").read_text(encoding="utf-8")

    assert "[data-logout]" in js
    assert "/api/v1/auth/logout" in js


def test_despues_del_logout_vuelve_a_pedir_login():
    cliente = _registrado()
    assert cliente.post("/api/v1/auth/logout").status_code == 200

    r = cliente.get("/resumen", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
