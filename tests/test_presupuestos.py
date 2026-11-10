"""Presupuestos: lo esencial del servicio, la API y las pantallas."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.presupuestos import PresupuestoEntrada
from app.services import movimientos, presupuestos
from app.services.comun import ErrorValidacion
from app.web import formato

client = TestClient(app)
U = 1
MERCADO, TRANSPORTE, ARRIENDO, OCIO, SALARIO = 3, 4, 5, 6, 1


def _mes_actual():
    hoy = movimientos.hoy()
    return hoy.year, hoy.month


def _entrada(**montos):
    return PresupuestoEntrada.model_validate(
        {"montos": [{"categoria_id": cid, "monto": str(m)} for cid, m in montos.values()]})


def test_un_mes_sin_presupuesto_no_esta_creado():
    anio, mes = _mes_actual()
    p = presupuestos.del_mes(U, anio, mes)

    assert not p.creado
    assert p.total == 0
    assert len(p.dias) >= 28


@pytest.mark.parametrize(
    ("hoy", "esperado"),
    [(date(2027, 1, 10), (2026, 12)), (date(2026, 11, 15), (2026, 10))],
)
def test_mes_anterior_cruza_el_anio_en_enero(hoy, esperado):
    assert presupuestos._mes_anterior(hoy) == esperado


def test_el_mes_anterior_trae_el_ejemplo_con_sus_estados():
    anio, mes = presupuestos._mes_anterior(movimientos.hoy())
    p = presupuestos.del_mes(U, anio, mes)
    estados = {c.categoria.nombre: c.estado for c in p.categorias}

    assert p.total == Decimal("2000000")
    assert p.gastado == Decimal("1874300")
    assert estados == {"Mercado": "alerta", "Transporte": "ok", "Arriendo": "alerta", "Ocio": "excedido"}


@pytest.mark.parametrize("pct, estado", [(0, "ok"), (79.9, "ok"), (80, "alerta"), (100, "alerta"), (100.1, "excedido")])
def test_estado_segun_el_porcentaje(pct, estado):
    assert presupuestos._estado(pct) == estado


def test_guardar_ignora_las_categorias_en_cero_y_suma_el_total():
    anio, mes = _mes_actual()
    p = presupuestos.guardar(U, anio, mes, _entrada(a=(MERCADO, 450000), b=(OCIO, 0), c=(ARRIENDO, 1100000)))

    assert p.creado
    assert [c.categoria.id for c in p.categorias] == [MERCADO, ARRIENDO]
    assert p.total == Decimal("1550000")


def test_guardar_valida_las_reglas():
    anio, mes = _mes_actual()
    with pytest.raises(ErrorValidacion) as vacio:
        presupuestos.guardar(U, anio, mes, _entrada(a=(MERCADO, 0)))
    with pytest.raises(ErrorValidacion) as ingreso:
        presupuestos.guardar(U, anio, mes, _entrada(a=(SALARIO, 100)))
    with pytest.raises(ErrorValidacion) as futuro:
        presupuestos.guardar(U, anio + 1, mes, _entrada(a=(MERCADO, 100)))

    assert "general" in vacio.value.errores
    assert "general" in ingreso.value.errores
    assert "general" in futuro.value.errores


def test_api_guarda_y_responde_errores_por_campo():
    anio, mes = _mes_actual()
    ok = client.put(f"/api/v1/presupuestos/{anio}/{mes}", json={"montos": [{"categoria_id": MERCADO, "monto": "450000"}]})
    malo = client.put(f"/api/v1/presupuestos/{anio}/{mes}", json={"montos": [{"categoria_id": MERCADO, "monto": "-5"}]})

    assert ok.status_code == 200 and ok.json()["creado"] is True
    assert malo.status_code == 422 and "monto_3" in malo.json()["errores"]


def test_resumen_muestra_la_invitacion_y_luego_la_barra():
    antes = client.get("/resumen").text
    anio, mes = _mes_actual()
    presupuestos.guardar(U, anio, mes, _entrada(a=(MERCADO, 450000)))
    despues = client.get("/resumen").text

    assert "Nuevo mes, nuevo presupuesto" in antes
    assert "Nuevo mes, nuevo presupuesto" not in despues
    assert "Te quedan $450.000" in despues


def test_presupuestos_muestra_el_vacio_y_luego_el_detalle():
    vacio = client.get("/presupuestos").text
    anio, mes = presupuestos._mes_anterior(movimientos.hoy())
    lleno = client.get(f"/presupuestos?anio={anio}&mes={mes}").text

    assert "Añade un presupuesto" in vacio
    assert "Te pasaste por $30.000" in lleno  # Ocio: $180.000 de $150.000
    assert "Editar presupuesto" in lleno


def test_presupuestos_tiene_el_calendario_del_mes():
    anio, mes = presupuestos._mes_anterior(movimientos.hoy())
    html = client.get(f"/presupuestos?anio={anio}&mes={mes}").text

    assert f"Gastos de {formato.nombre_mes(mes)}" in html and "data-dia=" in html
    anio_actual, mes_actual = _mes_actual()
    presupuestos.guardar(U, anio_actual, mes_actual, _entrada(a=(MERCADO, 450000)))
    assert f"Gastos en lo que va de {formato.nombre_mes(mes_actual)}" in client.get("/presupuestos").text


def test_crear_presupuesto_vuelve_a_presupuestos_salvo_desde_el_resumen():
    assert 'data-volver="/presupuestos?' in client.get("/presupuestos/nuevo").text
    assert 'data-volver="/presupuestos?' in client.get("/presupuestos/nuevo?volver=otra").text
    assert 'data-volver="/resumen?' in client.get("/presupuestos/nuevo?volver=resumen").text


def test_crear_presupuesto_lista_solo_categorias_de_gasto():
    html = client.get("/presupuestos/nuevo?volver=resumen").text

    assert 'id="monto-3"' in html  # Mercado
    assert 'id="monto-1"' not in html  # Salario
    assert "Crear presupuesto" in html
