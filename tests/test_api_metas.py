"""API JSON de metas de ahorro: crear, editar, eliminar, aportar, retirar y borrar aportes."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import movimientos

client = TestClient(app)
HOY = date(2026, 11, 16)


@pytest.fixture(autouse=True)
def _hoy(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: HOY)


def _crear(nombre="Viaje", objetivo="2000000", fecha_limite="2026-12-31"):
    r = client.post("/api/v1/metas", json={"nombre": nombre, "objetivo": objetivo, "fecha_limite": fecha_limite})
    assert r.status_code == 201, r.json()
    return r.json()["id"]


def test_crear_y_listar():
    id = _crear()

    panel = client.get("/api/v1/metas").json()
    [m] = panel["metas"]
    assert m["meta"]["id"] == id
    assert m["meta"]["nombre"] == "Viaje"
    assert m["ahorrado"] == "0"
    assert m["estado"] == "al_dia"
    assert m["por_mes"] == "1000000"  # noviembre y diciembre
    assert panel["total_objetivo"] == "2000000"


def test_errores_por_campo():
    r = client.post("/api/v1/metas", json={"nombre": "", "objetivo": "0", "fecha_limite": "2020-01-01"})

    assert r.status_code == 422
    assert set(r.json()["errores"]) == {"nombre", "objetivo", "fecha_limite"}


@pytest.mark.parametrize("cuerpo", [
    None, [], {"nombre": "Viaje"}, {"nombre": "Viaje", "objetivo": "abc"},
    {"nombre": "Viaje", "objetivo": "1000", "fecha_limite": "31/12/2026"},
])
def test_cuerpo_invalido_da_errores_legibles(cuerpo):
    r = client.post("/api/v1/metas", json=cuerpo)

    assert r.status_code == 422
    assert "errores" in r.json()


def test_editar_y_eliminar():
    id = _crear()

    r = client.put(f"/api/v1/metas/{id}", json={"nombre": "Carro", "objetivo": "5000000", "fecha_limite": None})
    assert r.status_code == 200
    assert r.json()["nombre"] == "Carro"
    assert client.delete(f"/api/v1/metas/{id}").status_code == 204
    assert client.get("/api/v1/metas").json()["metas"] == []
    assert client.delete(f"/api/v1/metas/{id}").status_code == 404
    assert client.put(f"/api/v1/metas/{id}", json={"nombre": "X", "objetivo": "1"}).status_code == 404


def test_aportar_retirar_y_borrar():
    id = _crear()

    r = client.post(f"/api/v1/metas/{id}/aportes", json={"monto": "300000", "fecha": "2026-11-16"})
    assert r.status_code == 201
    aporte = r.json()["id"]
    r = client.post(f"/api/v1/metas/{id}/aportes", json={"monto": "50000", "fecha": "2026-11-16", "retiro": True})
    assert r.status_code == 201
    assert r.json()["monto"] == "-50000"
    assert client.get("/api/v1/metas").json()["metas"][0]["ahorrado"] == "250000"

    r = client.post(f"/api/v1/metas/{id}/aportes", json={"monto": "999999", "fecha": "2026-11-16", "retiro": True})
    assert r.status_code == 422
    assert r.json()["errores"]["monto"] == "Solo tienes $250.000 ahorrados en esta meta."

    r = client.delete(f"/api/v1/metas/{id}/aportes/{aporte}")
    assert r.status_code == 422  # quedaría en -50.000
    assert "general" in r.json()["errores"]


def test_borrar_aporte():
    id = _crear()
    aporte = client.post(f"/api/v1/metas/{id}/aportes", json={"monto": "1000", "fecha": "2026-11-16"}).json()["id"]

    assert client.delete(f"/api/v1/metas/{id}/aportes/{aporte}").status_code == 204
    assert client.delete(f"/api/v1/metas/{id}/aportes/{aporte}").status_code == 404


def test_aporte_con_cuerpo_invalido():
    id = _crear()

    r = client.post(f"/api/v1/metas/{id}/aportes", json={"monto": "mucho", "fecha": "ayer"})
    assert r.status_code == 422
    assert set(r.json()["errores"]) == {"monto", "fecha"}
    assert client.post("/api/v1/metas/999/aportes", json={"monto": "1", "fecha": "2026-11-16"}).status_code == 404
