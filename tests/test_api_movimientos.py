"""API JSON de movimientos: la usa el diálogo con fetch y es el contrato con el backend."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import movimientos as servicio

client = TestClient(app)
URL = "/api/v1/movimientos"


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(servicio, "hoy", lambda: date(2026, 11, 15))


def cuerpo(**cambios):
    return {"tipo": "gasto", "monto": "50000", "categoria_id": 3, "cuenta_id": 1,
            "fecha": "2026-10-20", "descripcion": "Panadería"} | cambios


def test_crear_devuelve_201_y_aparece_en_la_lista():
    r = client.post(URL, json=cuerpo())

    assert r.status_code == 201
    creado = r.json()
    assert creado["categoria"] == {"id": 3, "nombre": "Mercado", "tipo": "gasto"}
    assert creado["monto"] == "50000"
    lista = client.get(URL, params={"anio": 2026, "mes": 10}).json()
    assert creado["id"] in [m["id"] for m in lista["movimientos"]]
    assert lista["gastos"] == "1924300"


def test_lista_con_filtros():
    lista = client.get(URL, params={"anio": 2026, "mes": 10, "tipo": "ingreso"}).json()

    assert lista["filtros"]["tipo"] == "ingreso"
    assert [m["descripcion"] for m in lista["movimientos"]] == ["Salario"]


@pytest.mark.parametrize("monto", [0, -5, "abc", "10.555", None])
def test_monto_invalido(monto):
    r = client.post(URL, json=cuerpo(monto=monto))

    assert r.status_code == 422
    assert r.json()["errores"]["monto"] == "Escribe un monto mayor que 0."


@pytest.mark.parametrize(
    ("cambios", "campo", "mensaje"),
    [
        ({"tipo": "otro"}, "tipo", "Elige gasto o ingreso."),
        ({"fecha": "ayer"}, "fecha", "Escribe una fecha válida."),
        ({"categoria_id": 1}, "categoria_id", "Esa categoría es de ingresos."),
        ({"cuenta_id": None}, "cuenta_id", "Elige una cuenta."),
        ({"fecha": "2026-12-01"}, "fecha", "La fecha no puede ser futura."),
    ],
)
def test_errores_por_campo(cambios, campo, mensaje):
    r = client.post(URL, json=cuerpo(**cambios))

    assert r.status_code == 422
    assert r.json()["errores"][campo] == mensaje


def test_cuerpo_que_no_es_objeto():
    assert client.post(URL, json=[1, 2]).status_code == 422


def test_editar_y_eliminar():
    creado = client.post(URL, json=cuerpo()).json()

    editado = client.put(f"{URL}/{creado['id']}", json=cuerpo(monto="75000", descripcion="Pan"))
    assert editado.status_code == 200
    assert editado.json()["monto"] == "75000" and editado.json()["descripcion"] == "Pan"

    assert client.delete(f"{URL}/{creado['id']}").status_code == 204
    assert client.delete(f"{URL}/{creado['id']}").status_code == 404


def test_put_inexistente_404():
    assert client.put(f"{URL}/9999", json=cuerpo()).status_code == 404


@pytest.mark.parametrize("monto", ["1E+30", "1e400", "9" * 5000, "1000000000000"])
def test_monto_enorme_se_rechaza_y_no_rompe_el_mes(monto):
    r = client.post(URL, json=cuerpo(monto=monto))

    assert r.status_code == 422
    assert "monto" in r.json()["errores"]
    assert client.get("/movimientos?anio=2026&mes=10").status_code == 200
    assert client.get("/resumen?anio=2026&mes=10").status_code == 200


def test_monto_con_exponente_se_guarda_normalizado():
    creado = client.post(URL, json=cuerpo(monto="1e5")).json()

    assert creado["monto"] == "100000"
