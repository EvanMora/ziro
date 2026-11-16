"""API JSON de categorías: la usa el diálogo de la sección con fetch."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import movimientos

client = TestClient(app)
URL = "/api/v1/categorias"


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 11, 15))


def crear(nombre="Mascotas", tipo="gasto"):
    r = client.post(URL, json={"nombre": nombre, "tipo": tipo})
    assert r.status_code == 201
    return r.json()


def con_movimiento(categoria_id):
    r = client.post("/api/v1/movimientos", json={"tipo": "gasto", "monto": "50000", "categoria_id": categoria_id,
                                                 "cuenta_id": 1, "fecha": "2026-10-20"})
    assert r.status_code == 201
    return r.json()


def test_crear_y_listar():
    creada = crear()

    assert creada == {"id": creada["id"], "nombre": "Mascotas", "tipo": "gasto", "predeterminada": False}
    lista = client.get(URL).json()
    assert len(lista) == 8 and lista[-1] == creada
    assert lista[0] == {"id": 1, "nombre": "Salario", "tipo": "ingreso", "predeterminada": True}


@pytest.mark.parametrize(
    ("cuerpo", "errores"),
    [
        ({"nombre": "", "tipo": "gasto"}, {"nombre": "Escribe un nombre."}),
        ({"nombre": 5, "tipo": "gasto"}, {"nombre": "Escribe un nombre."}),
        ({"nombre": "Mascotas", "tipo": "otro"}, {"tipo": "Elige gasto o ingreso."}),
        ({"tipo": "gasto"}, {"nombre": "Escribe un nombre."}),
        ({"nombre": "Ocio", "tipo": "gasto"}, {"nombre": "Ya hay una categoría de gastos con ese nombre."}),
    ],
)
def test_errores_por_campo(cuerpo, errores):
    r = client.post(URL, json=cuerpo)

    assert r.status_code == 422
    assert r.json() == {"errores": errores}


def test_cuerpo_que_no_es_objeto():
    assert client.post(URL, json=["Mascotas"]).status_code == 422


def test_editar():
    creada = crear()

    r = client.put(f"{URL}/{creada['id']}", json={"nombre": "Gatos", "tipo": "gasto"})

    assert r.status_code == 200 and r.json()["nombre"] == "Gatos"


def test_predeterminadas_responden_403():
    put = client.put(f"{URL}/3", json={"nombre": "Comida", "tipo": "gasto"})
    delete = client.delete(f"{URL}/3")

    for r in (put, delete):
        assert r.status_code == 403
        assert r.json() == {"errores": {"general": "Las categorías predeterminadas no se pueden cambiar ni eliminar."}}


def test_inexistente_404():
    assert client.put(f"{URL}/999", json={"nombre": "X", "tipo": "gasto"}).status_code == 404
    assert client.delete(f"{URL}/999").status_code == 404


def test_eliminar_sin_movimientos():
    creada = crear()

    assert client.delete(f"{URL}/{creada['id']}").status_code == 204
    assert client.delete(f"{URL}/{creada['id']}").status_code == 404


@pytest.mark.parametrize(("mover_a", "mensaje"), [
    (None, "Tiene 1 movimiento. Elige a qué categoría pasarlos."),
    ("abc", "Elige otra categoría."),
    ("9" * 50, "Elige otra categoría."),
    ("1", "Elige una categoría de gastos."),
])
def test_eliminar_con_movimientos_sin_destino_valido(mover_a, mensaje):
    creada = crear()
    con_movimiento(creada["id"])

    params = {"mover_a": mover_a} if mover_a else {}
    r = client.delete(f"{URL}/{creada['id']}", params=params)

    assert r.status_code == 422
    assert r.json() == {"errores": {"mover_a": mensaje}}


def test_eliminar_pasando_los_movimientos():
    creada = crear()
    m = con_movimiento(creada["id"])

    assert client.delete(f"{URL}/{creada['id']}", params={"mover_a": 7}).status_code == 204
    lista = client.get("/api/v1/movimientos", params={"anio": 2026, "mes": 10}).json()
    movido = next(x for x in lista["movimientos"] if x["id"] == m["id"])
    assert movido["categoria"] == {"id": 7, "nombre": "Otros gastos", "tipo": "gasto"}
