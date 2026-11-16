"""Todos los endpoints de la API exigen sesión: sin cookie de sesión responden 401.

La excepción son los de /api/v1/auth (login, registro, logout): son públicos por diseño.
Los de transferencias se llaman igual que los demás (Depends(usuario_requerido)).
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _anonimo() -> TestClient:
    """Un cliente nuevo: sin cookie de sesión."""
    return TestClient(app)


# (método, url) de cada ruta de la API que exige sesión. El login, el registro y el logout de
# /api/v1/auth son públicos y no van aquí.
_ENDPOINTS_PROTEGIDOS = [
    ("GET", "/api/v1/movimientos?anio=2026&mes=11"),
    ("POST", "/api/v1/movimientos"),
    ("PUT", "/api/v1/movimientos/1"),
    ("DELETE", "/api/v1/movimientos/1"),
    ("GET", "/api/v1/cuentas"),
    ("POST", "/api/v1/cuentas"),
    ("PUT", "/api/v1/cuentas/1"),
    ("DELETE", "/api/v1/cuentas/1"),
    ("POST", "/api/v1/cuentas/1/pagos"),
    ("PUT", "/api/v1/pagos/1"),
    ("DELETE", "/api/v1/pagos/1"),
    ("GET", "/api/v1/cuentas/transferencias"),
    ("POST", "/api/v1/cuentas/transferencias"),
    ("GET", "/api/v1/cuentas/transferencias/1"),
    ("PUT", "/api/v1/cuentas/transferencias/1"),
    ("DELETE", "/api/v1/cuentas/transferencias/1"),
    ("GET", "/api/v1/categorias"),
    ("POST", "/api/v1/categorias"),
    ("PUT", "/api/v1/categorias/1"),
    ("DELETE", "/api/v1/categorias/1"),
    ("POST", "/api/v1/ia/interpretar-movimiento"),
    ("GET", "/api/v1/ia/analisis-mes"),
    ("GET", "/api/v1/presupuestos/2026/11"),
    ("PUT", "/api/v1/presupuestos/2026/11"),
]


@pytest.mark.parametrize(("metodo", "url"), _ENDPOINTS_PROTEGIDOS,
                         ids=[f"{m} {u.split('?')[0]}" for m, u in _ENDPOINTS_PROTEGIDOS])
def test_api_sin_sesion_responde_401(metodo, url):
    r = _anonimo().request(metodo, url, json={})

    assert r.status_code == 401
    assert r.json()["detail"]
