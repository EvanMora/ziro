"""Sesión: vence según «Recordarme», se renueva al entrar, ignora cookies viejas o de usuarios borrados
y exige SECRET_KEY en producción (spec 2026-11-16-crear-cuenta-design.md, sección 4)."""
import json
from base64 import b64decode, b64encode
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from starlette.middleware.sessions import SessionMiddleware

from app import main
from app.api import auth as api_auth
from app.schemas.auth import UsuarioSesion
from app.services import database, usuarios
from app.web import sesion
from app.web.sesion import SinSesion, usuario_actual

pytestmark = pytest.mark.sin_plantilla


def _app_de_prueba() -> FastAPI:
    """La API de auth y una ruta protegida, con la misma sesión y el mismo manejador de la app."""
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key=main.SECRET_KEY, max_age=main.MAX_AGE_COOKIE)
    app.add_exception_handler(SinSesion, main.sin_sesion)
    app.include_router(api_auth.router)

    @app.get("/api/v1/yo")
    def yo(usuario: UsuarioSesion = Depends(usuario_actual)):
        return usuario

    @app.get("/pagina")
    def pagina(usuario: UsuarioSesion = Depends(usuario_actual)):
        return usuario

    return app


@pytest.fixture
def cliente():
    usuarios.crear("ana@x.com", "secreta123", "Ana Gómez")
    return TestClient(_app_de_prueba())


def _entrar(cliente, recordar=False):
    r = cliente.post("/api/v1/auth/login",
                     json={"email": "ana@x.com", "password": "secreta123", "recordar": recordar})
    assert r.status_code == 200
    return r


def _adelantar(monkeypatch, delta: timedelta):
    real = sesion.ahora()
    monkeypatch.setattr(sesion, "ahora", lambda: real + delta)


def _cookie(datos: dict) -> str:
    """Una cookie de sesión firmada como la firma Starlette (para simular cookies viejas)."""
    contenido = b64encode(json.dumps(datos).encode("utf-8"))
    return TimestampSigner(str(main.SECRET_KEY)).sign(contenido).decode("utf-8")


def test_con_sesion_responde_el_usuario(cliente):
    _entrar(cliente)

    r = cliente.get("/api/v1/yo")
    assert r.status_code == 200
    assert r.json()["correo"] == "ana@x.com"
    assert r.json()["iniciales"] == "AG"


def test_sin_sesion_la_api_da_401_y_la_pagina_lleva_al_login(cliente):
    r = cliente.get("/api/v1/yo")
    assert r.status_code == 401
    assert r.json() == {"detail": "Inicia sesión para continuar."}

    r = cliente.get("/pagina", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_sesion_dura_12_horas_sin_recordar(cliente, monkeypatch):
    _entrar(cliente)

    _adelantar(monkeypatch, timedelta(hours=11, minutes=59))
    assert cliente.get("/api/v1/yo").status_code == 200
    _adelantar(monkeypatch, timedelta(hours=12, seconds=1))
    assert cliente.get("/api/v1/yo").status_code == 401


def test_sesion_dura_30_dias_con_recordar(cliente, monkeypatch):
    _entrar(cliente, recordar=True)

    _adelantar(monkeypatch, timedelta(days=29))
    assert cliente.get("/api/v1/yo").status_code == 200
    _adelantar(monkeypatch, timedelta(days=30, seconds=1))
    assert cliente.get("/api/v1/yo").status_code == 401


def test_sesion_vencida_no_revive(cliente, monkeypatch):
    _entrar(cliente)
    _adelantar(monkeypatch, timedelta(hours=13))
    assert cliente.get("/api/v1/yo").status_code == 401

    monkeypatch.undo()  # el reloj vuelve a hoy: la sesión vencida se borró y no vuelve
    assert cliente.get("/api/v1/yo").status_code == 401


@pytest.mark.parametrize("datos", [
    {"usuario_id": 1},  # cookie de antes, sin "expira"
    {"usuario_id": "1", "expira": "mañana"},
    {"usuario_id": None, "expira": 9e18},
    {"expira": 9e18},
])
def test_cookie_mal_formada_no_es_sesion(cliente, datos):
    cliente.cookies.set("session", _cookie(datos))

    assert cliente.get("/api/v1/yo").status_code == 401


def test_usuario_borrado_pierde_la_sesion(cliente):
    _entrar(cliente)
    database.reiniciar()  # el usuario ya no existe

    assert cliente.get("/api/v1/yo").status_code == 401


def test_sesion_se_renueva_al_entrar(cliente):
    cliente.cookies.set("session", _cookie({"intruso": "valor", "usuario_id": 99, "expira": 9e18}))
    r = _entrar(cliente)

    contenido = TimestampSigner(str(main.SECRET_KEY)).unsign(r.cookies["session"])
    sesion_nueva = json.loads(b64decode(contenido))
    assert set(sesion_nueva) == {"usuario_id", "expira"}
    assert sesion_nueva["usuario_id"] == 1


def test_logout_cierra_la_sesion(cliente):
    _entrar(cliente)
    assert cliente.post("/api/v1/auth/logout").status_code == 200

    assert cliente.get("/api/v1/yo").status_code == 401


@pytest.mark.parametrize("clave", [None, "", "x" * 31])
def test_secret_key_en_produccion_obligatoria(monkeypatch, clave):
    monkeypatch.setenv("ENVIRONMENT", "production")
    if clave is None:
        monkeypatch.delenv("SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("SECRET_KEY", clave)

    with pytest.raises(RuntimeError):
        main.clave_secreta()


def test_secret_key_en_produccion_valida(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 32)

    assert main.clave_secreta() == "x" * 32


def test_secret_key_en_desarrollo_se_genera(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.warns(UserWarning):
        una = main.clave_secreta()
    with pytest.warns(UserWarning):
        otra = main.clave_secreta()
    assert len(una) >= 32
    assert una != otra


def test_la_app_no_trae_clave_fija():
    assert "desarrollo-inseguro-cambiar" not in open(main.__file__, encoding="utf-8").read()
