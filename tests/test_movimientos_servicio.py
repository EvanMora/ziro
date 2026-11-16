"""Servicio de movimientos: datos de prueba, filtros, totales y reglas de negocio.
Deben seguir pasando cuando el almacén en memoria se cambie por la base de datos."""
from datetime import date
from decimal import Decimal

import pytest

from app.schemas.movimientos import FiltrosMovimientos, MovimientoEntrada
from app.services import movimientos as servicio
from app.services.movimientos import ErrorValidacion, NoEncontrado


@pytest.fixture(autouse=True)
def almacen_limpio(monkeypatch):
    servicio.reiniciar()
    monkeypatch.setattr(servicio, "hoy", lambda: date(2026, 11, 15))
    yield
    servicio.reiniciar()


def entrada(**cambios) -> MovimientoEntrada:
    datos = {"tipo": "gasto", "monto": Decimal("50000"), "categoria_id": 3, "cuenta_id": 1,
             "fecha": date(2026, 10, 20), "descripcion": "Panadería"}
    return MovimientoEntrada(**(datos | cambios))


def test_octubre_tiene_los_datos_de_prueba():
    lista = servicio.listar(1, 2026, 10)

    assert len(lista.movimientos) == 8
    assert lista.ingresos == Decimal("3200000")
    assert lista.gastos == Decimal("1874300")


def test_orden_del_mas_reciente_al_mas_antiguo():
    servicio.crear(1, entrada(fecha=date(2026, 10, 31), descripcion="Después del salario"))
    movimientos = servicio.listar(1, 2026, 10).movimientos
    claves = [(m.fecha, m.id) for m in movimientos]

    assert claves == sorted(claves, reverse=True)
    assert movimientos[0].descripcion == "Después del salario"


def test_mes_actual_sin_dias_futuros():
    fechas = [m.fecha for m in servicio.listar(1, 2026, 11).movimientos]

    assert fechas == [date(2026, 11, 15), date(2026, 11, 10)]


def test_filtra_por_tipo_cuenta_y_categoria():
    gastos = servicio.listar(1, 2026, 10, FiltrosMovimientos(tipo="gasto"))
    efectivo = servicio.listar(1, 2026, 10, FiltrosMovimientos(cuenta_id=3))
    ocio = servicio.listar(1, 2026, 10, FiltrosMovimientos(categoria_id=6))

    assert gastos.ingresos == 0 and gastos.gastos == Decimal("1874300")
    assert {m.cuenta.nombre for m in efectivo.movimientos} == {"Efectivo"}
    assert ocio.gastos == Decimal("180000")
    assert ocio.filtros.categoria_id == 6


def test_busqueda_sin_tildes_ni_mayusculas():
    servicio.crear(1, entrada(descripcion="Café"))

    encontrados = servicio.listar(1, 2026, 10, FiltrosMovimientos(q="CAFE")).movimientos
    por_categoria = servicio.listar(1, 2026, 10, FiltrosMovimientos(q="transp")).movimientos
    espacios = servicio.listar(1, 2026, 10, FiltrosMovimientos(q="   "))

    assert [m.descripcion for m in encontrados] == ["Café"]
    assert {m.categoria.nombre for m in por_categoria} == {"Transporte"}
    assert espacios.gastos == servicio.listar(1, 2026, 10).gastos


@pytest.mark.parametrize(
    ("cambios", "campo", "mensaje"),
    [
        ({"monto": Decimal("0")}, "monto", "Escribe un monto mayor que 0."),
        ({"monto": Decimal("-5")}, "monto", "Escribe un monto mayor que 0."),
        ({"categoria_id": 99}, "categoria_id", "Elige una categoría."),
        ({"categoria_id": 1}, "categoria_id", "Esa categoría es de ingresos."),
        ({"tipo": "ingreso", "categoria_id": 3}, "categoria_id", "Esa categoría es de gastos."),
        ({"cuenta_id": 99}, "cuenta_id", "Elige una cuenta."),
        ({"fecha": date(2026, 11, 16)}, "fecha", "La fecha no puede ser futura."),
        ({"descripcion": "x" * 81}, "descripcion", "Máximo 80 caracteres."),
    ],
)
def test_crear_valida_reglas(cambios, campo, mensaje):
    with pytest.raises(ErrorValidacion) as error:
        servicio.crear(1, entrada(**cambios))

    assert error.value.errores[campo] == mensaje


def test_descripcion_sin_espacios_a_los_lados():
    assert servicio.crear(1, entrada(descripcion="  Pan  ")).descripcion == "Pan"


def test_actualizar_a_otro_mes_lo_mueve():
    taxi = next(m for m in servicio.listar(1, 2026, 10).movimientos if m.descripcion == "Taxi")

    movido = servicio.actualizar(1, taxi.id, entrada(
        tipo="gasto", monto=taxi.monto, categoria_id=taxi.categoria.id, cuenta_id=taxi.cuenta.id,
        fecha=date(2026, 9, 5), descripcion="Taxi"))

    assert movido.id == taxi.id
    assert taxi.id not in {m.id for m in servicio.listar(1, 2026, 10).movimientos}
    assert taxi.id in {m.id for m in servicio.listar(1, 2026, 9).movimientos}
    assert servicio.obtener(1, taxi.id).fecha == date(2026, 9, 5)


def test_eliminar_y_no_encontrado():
    nuevo = servicio.crear(1, entrada())
    servicio.eliminar(1, nuevo.id)

    assert servicio.obtener(1, nuevo.id) is None
    with pytest.raises(NoEncontrado):
        servicio.eliminar(1, 9999)
    with pytest.raises(NoEncontrado):
        servicio.actualizar(1, 9999, entrada())


def test_catalogo():
    cuentas, categorias = servicio.catalogo(1)

    assert [c.nombre for c in cuentas] == ["Cuenta de ahorros", "Billetera digital", "Efectivo", "Tarjeta de crédito"]
    assert {c.nombre: c.tipo for c in categorias} == {
        "Salario": "ingreso", "Otros ingresos": "ingreso", "Mercado": "gasto", "Transporte": "gasto",
        "Arriendo": "gasto", "Ocio": "gasto", "Otros gastos": "gasto",
    }
