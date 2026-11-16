"""Página de Cuentas: totales, dinero y tarjetas en dos columnas, y el diálogo de cuenta."""
import json
import re
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.cuentas import CuentaEntrada
from app.schemas.movimientos import MovimientoEntrada
from app.services import cuentas, movimientos

client = TestClient(app)
U = 1


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 11, 15))


def html():
    return client.get("/cuentas").text


def tarjeta(nombre, dia_pago, saldo="100000"):
    return cuentas.crear(U, CuentaEntrada(nombre=nombre, tipo="tarjeta", icono="tarjeta", tono="azul",
                                          saldo=Decimal(saldo), cupo=Decimal("1000000"), dia_pago=dia_pago))


def test_totales():
    h = html()

    assert "Tienes en total" in h and "$4.382.900" in h
    assert "Debes en tarjetas" in h and "−$840.000" in h
    assert "Te queda" in h and "+$3.542.900" in h


def test_columnas():
    h = html()

    assert ">Dinero<" in h and ">Tarjetas de crédito<" in h
    assert '<span class="sub">Cuenta de ahorros</span>' in h
    assert "−$1.100.000" not in h  # no hay movimientos sueltos, solo saldos
    assert "Pagar antes del 15 nov" in h
    assert ">Hoy<" in h
    assert "Disponible $2.160.000 de $3.000.000" in h
    assert "data-registrar-pago" in h


def test_sin_selector_de_mes():
    assert 'aria-label="Mes"' not in html()


def test_alerta_y_cupo_excedido():
    tarjeta("Visa", 30)
    h = html()
    assert h.count("cuentas-fecha--alerta") == 1  # la de hoy sí; la del día 30 no

    movimientos.crear(U, MovimientoEntrada(tipo="gasto", monto=Decimal("2500000"), categoria_id=3, cuenta_id=4,
                                           fecha=date(2026, 11, 14)))
    assert "Pasaste el cupo por $340.000" in html()


def test_al_dia():
    cuentas.registrar_pago(U, 4, cuentas.PagoEntrada(monto=Decimal("840000"), cuenta_origen_id=1,
                                                     fecha=date(2026, 11, 14)))
    h = html()

    assert "Al día" in h and "Pagar antes del" not in h


def test_sin_tarjetas():
    cuentas.eliminar(U, 4)
    h = html()

    assert "Agregar tarjeta" in h
    assert "Debes en tarjetas" not in h


def test_nombre_con_html_se_escapa():
    cuentas.crear(U, CuentaEntrada(nombre="<b>x</b>", tipo="efectivo", icono="billetes", tono="cafe",
                                   saldo=Decimal(0)))

    assert "<b>x</b>" not in html()


def test_dialogo_de_cuenta():
    h = html()

    assert 'id="dialogo-cuenta"' in h
    for icono in ["banco", "alcancia", "billetera", "celular", "billetes", "tarjeta", "monedas", "maletin"]:
        assert f'name="icono" value="{icono}"' in h
    for tono in ["azul", "indigo", "violeta", "ciruela", "petroleo", "cafe", "arena", "grafito"]:
        assert f'name="tono" value="{tono}"' in h
    assert "Si no coincide con tu banco, escribe el saldo real." in h


def test_datos_para_editar():
    datos = [json.loads(d) for d in re.findall(r"data-cuenta='([^']*)'", html())]

    ahorros = next(d for d in datos if d["id"] == 1)
    assert {k: v for k, v in ahorros.items() if k != "usos"} == {
        "id": 1, "nombre": "Cuenta de ahorros", "tipo": "ahorros", "icono": "banco", "tono": "azul",
        "saldo": "3612400", "cupo": None, "dia_pago": None, "pagos": 0}
    assert ahorros["usos"] > 0
    tarjeta = next(d for d in datos if d["id"] == 4)
    assert (tarjeta["saldo"], tarjeta["cupo"], tarjeta["dia_pago"]) == ("840000", "3000000", 15)


def test_dialogo_de_pago():
    h = html()

    assert 'id="dialogo-pago"' in h
    desde = h.split('id="pago-origen"', 1)[1].split("</select>", 1)[0]
    assert desde.count("<option value=\"") == 3 + 1  # "Elige una" y las 3 de dinero
    assert "Tarjeta de crédito" not in desde
    assert 'id="pago-fecha"' in h and 'max="2026-11-15"' in h
    datos = json.loads(re.search(r"data-cuentas-dinero='([^']*)'", h).group(1))
    assert {"id": 1, "nombre": "Cuenta de ahorros", "saldo": "3612400"} in datos
    tarjetas = json.loads(re.search(r"data-tarjetas='([^']*)'", h).group(1))
    assert tarjetas == [{"id": 4, "nombre": "Tarjeta de crédito", "deuda": "840000",
                         "fecha_texto": "Pagar antes del 15 nov"}]
    assert "js/pago-dialogo.js" in h
