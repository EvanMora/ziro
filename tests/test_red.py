"""La IP del visitante para el límite de intentos. En Vercel la app está detrás de su red y la IP de
la conexión es la de Vercel: la real llega en x-vercel-forwarded-for, que Vercel sobrescribe (nadie
la puede falsificar). Fuera de Vercel no se confía en ninguna cabecera."""
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.main import app
from app.web.red import ip_cliente

pytestmark = pytest.mark.sin_plantilla


def _request(cabeceras: dict[str, str] | None = None, cliente=("10.0.0.9", 1234)) -> Request:
    return Request({
        "type": "http", "method": "GET", "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (cabeceras or {}).items()],
        "client": cliente,
    })


@pytest.mark.parametrize(("cabecera", "esperada"), [
    ("190.1.2.3", "190.1.2.3"),
    ("190.1.2.3, 10.0.0.1", "190.1.2.3"),
    ("  190.1.2.3 ,10.0.0.1", "190.1.2.3"),
])
def test_en_vercel_usa_la_cabecera(monkeypatch, cabecera, esperada):
    monkeypatch.setenv("VERCEL", "1")

    assert ip_cliente(_request({"x-vercel-forwarded-for": cabecera})) == esperada


@pytest.mark.parametrize("cabeceras", [{}, {"x-vercel-forwarded-for": ""}, {"x-vercel-forwarded-for": " , "}])
def test_en_vercel_sin_cabecera_usa_la_conexion(monkeypatch, cabeceras):
    monkeypatch.setenv("VERCEL", "1")

    assert ip_cliente(_request(cabeceras)) == "10.0.0.9"


def test_fuera_de_vercel_ignora_la_cabecera(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    falsas = {"x-vercel-forwarded-for": "1.1.1.1", "x-forwarded-for": "2.2.2.2", "x-real-ip": "3.3.3.3"}

    assert ip_cliente(_request(falsas)) == "10.0.0.9"


def test_sin_cliente(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)

    assert ip_cliente(_request(cliente=None)) == "desconocida"


def test_limite_por_ip_en_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    cliente = TestClient(app)

    def login(correo: str, ip: str):
        return cliente.post("/api/v1/auth/login", json={"email": correo, "password": "mala-clave"},
                            headers={"x-vercel-forwarded-for": ip})

    for i in range(5):
        assert login(f"nadie{i}@x.com", "190.1.2.3").status_code == 401

    # Todas las peticiones llegan por la misma conexión (la de Vercel): el límite distingue por la
    # IP real, no bloquea a todo el mundo.
    assert login("otro@x.com", "190.1.2.3").status_code == 429
    assert login("otro@x.com", "190.9.9.9").status_code == 401
