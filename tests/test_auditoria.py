"""Errores encontrados en la auditoría del repositorio (2026-11-02). Cada prueba reproduce uno."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import movimientos

client = TestClient(app)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 11, 15))


TARJETA = {"nombre": "Visa", "tipo": "tarjeta", "icono": "tarjeta", "tono": "azul", "saldo": "0",
           "cupo": "1000000", "dia_pago": 5}
MOVIMIENTO = {"tipo": "gasto", "monto": "10000", "categoria_id": 3, "cuenta_id": 1, "fecha": "2026-11-10"}


# ---------- Montos que se redondean a 0 ----------

def test_pago_que_se_redondea_a_cero_se_rechaza():
    r = client.post("/api/v1/cuentas/4/pagos", json={"monto": "0.001", "cuenta_origen_id": 1, "fecha": "2026-11-10"})

    assert r.status_code == 422
    assert r.json()["errores"]["monto"] == "Escribe un monto mayor que 0."


def test_cupo_que_se_redondea_a_cero_se_rechaza():
    r = client.post("/api/v1/cuentas", json=TARJETA | {"cupo": "0.004"})

    assert r.status_code == 422
    assert r.json()["errores"]["cupo"] == "Escribe un cupo mayor que 0."


# ---------- Mes o año inválido en la URL ----------

@pytest.mark.parametrize("url", [
    "/movimientos?anio=2026&mes=13",
    "/movimientos?anio=abc&mes=1",
    "/resumen?anio=abc&mes=1",
    "/resumen?anio=2026&mes=0",
    "/categorias?anio=1999&mes=1",
    "/categorias?anio=2026&mes=%C2%B2",
])
def test_mes_invalido_en_la_url_muestra_el_mes_actual(url):
    r = client.get(url)

    assert r.status_code == 200
    assert "Noviembre 2026" in r.text


# ---------- Nombres con caracteres invisibles ----------

@pytest.mark.parametrize("nombre", ["​", "​​ ", "﻿", "⁠­"])
def test_nombre_invisible_de_categoria_y_cuenta(nombre):
    categoria = client.post("/api/v1/categorias", json={"nombre": nombre, "tipo": "gasto"})
    cuenta = client.post("/api/v1/cuentas", json=TARJETA | {"nombre": nombre})

    assert categoria.json()["errores"]["nombre"] == "Escribe un nombre."
    assert cuenta.json()["errores"]["nombre"] == "Escribe un nombre."


def test_caracteres_invisibles_no_esquivan_el_nombre_repetido():
    r = client.post("/api/v1/categorias", json={"nombre": "Mer​cado", "tipo": "gasto"})

    assert r.json()["errores"]["nombre"] == "Ya hay una categoría de gastos con ese nombre."


def test_caracteres_invisibles_se_quitan_al_guardar():
    categoria = client.post("/api/v1/categorias", json={"nombre": "​Mascotas​", "tipo": "gasto"}).json()
    movimiento = client.post("/api/v1/movimientos", json=MOVIMIENTO | {"descripcion": "​"}).json()
    emoji = client.post("/api/v1/categorias", json={"nombre": "Familia 👨‍👩‍👧", "tipo": "gasto"}).json()

    assert categoria["nombre"] == "Mascotas"
    assert movimiento["descripcion"] == ""
    assert emoji["nombre"] == "Familia 👨‍👩‍👧"  # la unión de los emojis se conserva


# ---------- Booleanos donde van números ----------

@pytest.mark.parametrize(("url", "cuerpo", "campo"), [
    ("/api/v1/cuentas", TARJETA | {"dia_pago": True}, "dia_pago"),
    ("/api/v1/cuentas/4/pagos", {"monto": "1000", "cuenta_origen_id": True, "fecha": "2026-11-10"}, "cuenta_origen_id"),
    ("/api/v1/movimientos", MOVIMIENTO | {"categoria_id": True}, "categoria_id"),
    ("/api/v1/movimientos", MOVIMIENTO | {"cuenta_id": True}, "cuenta_id"),
])
def test_true_no_cuenta_como_1(url, cuerpo, campo):
    r = client.post(url, json=cuerpo)

    assert r.status_code == 422
    assert campo in r.json()["errores"]


# ---------- Búsqueda por cuenta ----------

def test_la_busqueda_encuentra_por_nombre_de_cuenta():
    lista = client.get("/api/v1/movimientos", params={"anio": 2026, "mes": 10, "q": "EFECTIVO"}).json()

    assert sorted(m["descripcion"] for m in lista["movimientos"]) == ["Plaza de mercado", "Taxi"]
