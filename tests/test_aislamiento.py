"""Cada quien ve y toca solo sus datos: B no puede leer, cambiar, borrar ni usar lo de A aunque
conozca sus ids (spec 2026-11-16-crear-cuenta-design.md, sección 5). Con login real, sin la sesión
simulada de los demás tests."""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.services import database

pytestmark = pytest.mark.sin_plantilla

HOY = date.today().isoformat()
MERCADO = 3  # categoría predeterminada de gasto


def _registrado(correo: str) -> TestClient:
    cliente = TestClient(app, client=(correo, 1))  # IP distinta por usuario: el límite de registro es por IP
    r = cliente.post("/api/v1/auth/registro", json={"nombre": correo, "email": correo, "password": "secreta123"})
    assert r.status_code == 201
    return cliente


def _cuenta(cliente, nombre, tipo="ahorros", **extra):
    datos = {"nombre": nombre, "tipo": tipo, "icono": "banco", "tono": "azul", "saldo": "100000"} | extra
    r = cliente.post("/api/v1/cuentas", json=datos)
    assert r.status_code == 201, r.json()
    return r.json()["id"]


@pytest.fixture
def datos_de_a():
    """A con una cuenta, una tarjeta con un pago, una categoría propia, un movimiento y un
    presupuesto del mes."""
    a = _registrado("a@x.com")
    cuenta = _cuenta(a, "Ahorros A")
    tarjeta = _cuenta(a, "Tarjeta A", tipo="tarjeta", icono="tarjeta", saldo="0", cupo="500000", dia_pago=10)
    categoria = a.post("/api/v1/categorias", json={"nombre": "Mascotas", "tipo": "gasto"}).json()["id"]
    movimiento = a.post("/api/v1/movimientos", json={
        "tipo": "gasto", "monto": "1000.00", "categoria_id": categoria, "cuenta_id": cuenta, "fecha": HOY,
    }).json()["id"]
    a.post("/api/v1/movimientos", json={
        "tipo": "gasto", "monto": "5000.00", "categoria_id": MERCADO, "cuenta_id": tarjeta, "fecha": HOY})
    pago = a.post(f"/api/v1/cuentas/{tarjeta}/pagos",
                  json={"monto": "1000", "cuenta_origen_id": cuenta, "fecha": HOY}).json()["id"]
    hoy = date.today()
    r = a.put(f"/api/v1/presupuestos/{hoy.year}/{hoy.month}",
              json={"montos": [{"categoria_id": categoria, "monto": "50000"}]})
    assert r.status_code == 200, r.json()
    return {"cliente": a, "cuenta": cuenta, "tarjeta": tarjeta, "categoria": categoria,
            "movimiento": movimiento, "pago": pago}


def _foto(cliente) -> dict:
    hoy = date.today()
    return {
        "cuentas": cliente.get("/api/v1/cuentas").json(),
        "categorias": cliente.get("/api/v1/categorias").json(),
        "movimientos": cliente.get(f"/api/v1/movimientos?anio={hoy.year}&mes={hoy.month}").json(),
        "presupuesto": cliente.get(f"/api/v1/presupuestos/{hoy.year}/{hoy.month}").json(),
    }


def test_b_no_ve_lo_de_a(datos_de_a):
    b = _registrado("b@x.com")
    foto = _foto(b)

    assert foto["cuentas"]["dinero"] == [] and foto["cuentas"]["tarjetas"] == []
    assert len(foto["categorias"]) == 7
    assert foto["movimientos"]["movimientos"] == []
    assert foto["presupuesto"]["creado"] is False


def test_b_no_cambia_ni_borra_lo_de_a(datos_de_a):
    a, d = datos_de_a["cliente"], datos_de_a
    antes = _foto(a)
    b = _registrado("b@x.com")

    cuenta = {"nombre": "Robada", "tipo": "ahorros", "icono": "banco", "tono": "azul", "saldo": "0"}
    movimiento = {"tipo": "gasto", "monto": "1.00", "categoria_id": MERCADO, "cuenta_id": d["cuenta"], "fecha": HOY}
    intentos = [
        b.put(f"/api/v1/cuentas/{d['cuenta']}", json=cuenta),
        b.delete(f"/api/v1/cuentas/{d['cuenta']}"),
        b.put(f"/api/v1/categorias/{d['categoria']}", json={"nombre": "Robada", "tipo": "gasto"}),
        b.delete(f"/api/v1/categorias/{d['categoria']}"),
        b.put(f"/api/v1/movimientos/{d['movimiento']}", json=movimiento),
        b.delete(f"/api/v1/movimientos/{d['movimiento']}"),
        b.put(f"/api/v1/pagos/{d['pago']}", json={"monto": "1", "cuenta_origen_id": d["cuenta"], "fecha": HOY}),
        b.delete(f"/api/v1/pagos/{d['pago']}"),
        b.post(f"/api/v1/cuentas/{d['tarjeta']}/pagos",
               json={"monto": "1", "cuenta_origen_id": d["cuenta"], "fecha": HOY}),
    ]
    for r in intentos:
        assert r.status_code == 404, (r.request.method, r.request.url, r.status_code, r.text)

    assert _foto(a) == antes


def test_b_no_usa_ids_de_a_en_lo_suyo(datos_de_a):
    d = datos_de_a
    b = _registrado("b@x.com")
    propia = _cuenta(b, "Ahorros B")
    tarjeta_b = _cuenta(b, "Tarjeta B", tipo="tarjeta", icono="tarjeta", saldo="0", cupo="500000", dia_pago=10)

    r = b.post("/api/v1/movimientos", json={
        "tipo": "gasto", "monto": "1.00", "categoria_id": MERCADO, "cuenta_id": d["cuenta"], "fecha": HOY})
    assert r.status_code == 422 and "cuenta_id" in r.json()["errores"]

    r = b.post("/api/v1/movimientos", json={
        "tipo": "gasto", "monto": "1.00", "categoria_id": d["categoria"], "cuenta_id": propia, "fecha": HOY})
    assert r.status_code == 422 and "categoria_id" in r.json()["errores"]

    r = b.post(f"/api/v1/cuentas/{tarjeta_b}/pagos", json={"monto": "1", "cuenta_origen_id": d["cuenta"], "fecha": HOY})
    assert r.status_code == 422 and "cuenta_origen_id" in r.json()["errores"]

    r = b.delete(f"/api/v1/cuentas/{propia}?mover_a={d['cuenta']}")
    assert r.status_code in (204, 422)  # sin movimientos se borra; nunca pasa nada a la cuenta de A
    hoy = date.today()
    r = b.put(f"/api/v1/presupuestos/{hoy.year}/{hoy.month}",
              json={"montos": [{"categoria_id": d["categoria"], "monto": "1000"}]})
    assert r.status_code == 422


def test_b_no_pasa_sus_movimientos_a_una_cuenta_de_a(datos_de_a):
    d = datos_de_a
    b = _registrado("b@x.com")
    propia = _cuenta(b, "Ahorros B")
    b.post("/api/v1/movimientos", json={
        "tipo": "gasto", "monto": "1.00", "categoria_id": MERCADO, "cuenta_id": propia, "fecha": HOY})
    antes = _foto(d["cliente"])

    r = b.delete(f"/api/v1/cuentas/{propia}?mover_a={d['cuenta']}")
    assert r.status_code == 422
    assert _foto(d["cliente"]) == antes


def test_claves_foraneas_activas():
    # La base rechaza una fila que apunta a un usuario que no existe (en SQLite hay que pedirlo en
    # cada conexión con PRAGMA foreign_keys=ON; Postgres lo hace siempre).
    with pytest.raises(IntegrityError):
        with database.sesion() as db:
            db.execute(text("INSERT INTO categorias (usuario_id, nombre, tipo) VALUES (999, 'Huérfana', 'gasto')"))


def test_eliminar_categoria_con_presupuesto(datos_de_a):
    a, d = datos_de_a["cliente"], datos_de_a

    r = a.delete(f"/api/v1/categorias/{d['categoria']}?mover_a={MERCADO}")
    assert r.status_code == 204, r.text
    hoy = date.today()
    presupuesto = a.get(f"/api/v1/presupuestos/{hoy.year}/{hoy.month}").json()
    assert all(f["categoria"]["id"] != d["categoria"] for f in presupuesto["categorias"])


def test_b_no_reordena_los_otros_de_a(datos_de_a):
    a, d = datos_de_a["cliente"], datos_de_a
    otros = a.post("/api/v1/movimientos", json={
        "tipo": "gasto", "monto": "9000.00", "categoria_id": 7, "cuenta_id": d["cuenta"], "fecha": HOY,
        "descripcion": "Peluquería"}).json()["id"]
    b = _registrado("b@x.com")

    r = b.post("/api/v1/ia/ordenar-otros/aplicar", json={"movimientos": [otros], "categoria_id": MERCADO})
    assert r.status_code == 422
    hoy = date.today()
    movs = a.get(f"/api/v1/movimientos?anio={hoy.year}&mes={hoy.month}").json()["movimientos"]
    assert next(m for m in movs if m["id"] == otros)["categoria"]["id"] == 7
