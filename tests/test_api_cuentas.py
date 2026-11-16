"""API JSON de cuentas y pagos: la usan los diálogos de Cuentas y Movimientos con fetch."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import movimientos

client = TestClient(app)
URL = "/api/v1/cuentas"


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 11, 15))


def cuerpo(**cambios):
    return {"nombre": "Nequi", "tipo": "billetera", "icono": "celular", "tono": "ciruela", "saldo": "200000"} | cambios


def pago(**cambios):
    return {"monto": "300000", "cuenta_origen_id": 1, "fecha": "2026-11-12"} | cambios


def test_crear_y_listar():
    r = client.post(URL, json=cuerpo())

    assert r.status_code == 201
    creada = r.json()
    assert (creada["nombre"], creada["inicial"], creada["creada_en"]) == ("Nequi", "200000", "2026-11-15")
    panel = client.get(URL).json()
    assert panel["tienes"] == "4582900"
    assert [c["cuenta"]["nombre"] for c in panel["dinero"]][-1] == "Nequi"


@pytest.mark.parametrize(
    ("cambios", "errores"),
    [
        ({"nombre": 5}, {"nombre": "Escribe un nombre."}),
        ({"tipo": "otro"}, {"tipo": "Elige un tipo de cuenta."}),
        ({"icono": "x"}, {"icono": "Elige un ícono."}),
        ({"tono": "x"}, {"tono": "Elige un tono."}),
        ({"saldo": "abc"}, {"saldo": "Escribe un saldo válido."}),
        ({"tipo": "tarjeta", "cupo": "1000000", "dia_pago": "x"}, {"dia_pago": "Elige un día entre 1 y 31."}),
        ({"nombre": "efectivo"}, {"nombre": "Ya tienes una cuenta con ese nombre."}),
    ],
)
def test_errores_por_campo(cambios, errores):
    r = client.post(URL, json=cuerpo(**cambios))

    assert r.status_code == 422
    assert r.json() == {"errores": errores}


def test_cuerpo_que_no_es_objeto():
    assert client.post(URL, json=["Nequi"]).status_code == 422
    assert client.post(f"{URL}/4/pagos", json="300000").status_code == 422


def test_editar_y_eliminar():
    creada = client.post(URL, json=cuerpo()).json()

    r = client.put(f"{URL}/{creada['id']}", json=cuerpo(nombre="Nequi personal", saldo="150000"))
    assert r.status_code == 200 and r.json()["nombre"] == "Nequi personal"

    assert client.delete(f"{URL}/{creada['id']}").status_code == 204
    assert client.delete(f"{URL}/{creada['id']}").status_code == 404


def test_inexistente_404():
    assert client.put(f"{URL}/999", json=cuerpo()).status_code == 404
    assert client.delete(f"{URL}/999").status_code == 404


@pytest.mark.parametrize("mover_a", ["abc", "9" * 50])
def test_mover_a_invalido(mover_a):
    r = client.delete(f"{URL}/1", params={"mover_a": mover_a})

    assert r.status_code == 422
    assert r.json() == {"errores": {"mover_a": "Elige otra cuenta."}}


def test_eliminar_pasando_los_movimientos():
    assert client.delete(f"{URL}/3", params={"mover_a": 2}).status_code == 204
    nombres = [c["cuenta"]["nombre"] for c in client.get(URL).json()["dinero"]]
    assert "Efectivo" not in nombres


@pytest.mark.parametrize("monto", ["1E+30", "abc", -5, None])
def test_pago_con_monto_raro(monto):
    r = client.post(f"{URL}/4/pagos", json=pago(monto=monto))

    assert r.status_code == 422
    assert "monto" in r.json()["errores"]


def test_pago_a_cuenta_de_dinero_o_inexistente():
    r = client.post(f"{URL}/1/pagos", json=pago())
    assert r.status_code == 422
    assert r.json() == {"errores": {"general": "Solo se le pueden registrar pagos a una tarjeta."}}

    assert client.post(f"{URL}/999/pagos", json=pago()).status_code == 404


def test_pago_errores_de_forma():
    r = client.post(f"{URL}/4/pagos", json=pago(cuenta_origen_id="x", fecha="ayer"))

    assert r.json() == {"errores": {"cuenta_origen_id": "Elige de qué cuenta sale el pago.",
                                    "fecha": "Escribe una fecha válida."}}


def test_registrar_editar_y_eliminar_pago():
    r = client.post(f"{URL}/4/pagos", json=pago())
    assert r.status_code == 201
    creado = r.json()
    assert (creado["tarjeta"]["nombre"], creado["origen"]["nombre"]) == ("Tarjeta de crédito", "Cuenta de ahorros")
    assert client.get(URL).json()["debes"] == "540000"

    editado = client.put(f"/api/v1/pagos/{creado['id']}", json=pago(monto="840000"))
    assert editado.status_code == 200
    assert client.get(URL).json()["debes"] == "0"

    assert client.delete(f"/api/v1/pagos/{creado['id']}").status_code == 204
    assert client.delete(f"/api/v1/pagos/{creado['id']}").status_code == 404
    assert client.put(f"/api/v1/pagos/{creado['id']}", json=pago()).status_code == 404


@pytest.mark.parametrize(("saldo", "cupo", "inicial", "cupo_guardado"), [
    ("1E+3", "1E+6", "1000", "1000000"),
    ("840000.50", "3000000.00", "840000.50", "3000000"),
    ("0.001", "2000000", "0.00", "2000000"),
])
def test_saldo_y_cupo_se_guardan_normalizados(saldo, cupo, inicial, cupo_guardado):
    r = client.post(URL, json=cuerpo(nombre="Visa", tipo="tarjeta", icono="tarjeta", saldo=saldo, cupo=cupo,
                                     dia_pago=20))

    assert r.status_code == 201
    assert (r.json()["inicial"], r.json()["cupo"]) == (inicial, cupo_guardado)
