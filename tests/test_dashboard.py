"""Contrato del Resumen y filtros de formato. Estos tests deben seguir pasando cuando
services/dashboard.py deje los datos de prueba y use la base de datos."""
from datetime import date
from decimal import Decimal

from app.services.dashboard import CANTIDAD_RECIENTES, obtener_resumen
from app.web.formato import dinero, fecha_corta, porcentaje
from app.web.presentacion import vista_resumen


def test_resumen_cuadra():
    r = obtener_resumen(usuario_id=1, anio=2026, mes=10)

    assert r.saldo_total == sum(c.saldo for c in r.cuentas)
    assert r.gastos_mes == sum(g.total for g in r.gastos_por_categoria)
    assert all(isinstance(v, Decimal) for v in (r.saldo_total, r.ingresos_mes, r.gastos_mes))


def test_categorias_de_mayor_a_menor():
    totales = [g.total for g in obtener_resumen(1, 2026, 10).gastos_por_categoria]

    assert totales == sorted(totales, reverse=True)


def test_recientes_del_mes_y_del_mas_nuevo_al_mas_viejo():
    recientes = obtener_resumen(1, 2026, 2).movimientos_recientes
    fechas = [m.fecha for m in recientes]

    assert len(recientes) <= CANTIDAD_RECIENTES
    assert fechas == sorted(fechas, reverse=True)
    assert all(f.year == 2026 and f.month == 2 for f in fechas)
    assert all(m.monto > 0 for m in recientes)


def test_dinero():
    assert dinero(Decimal("1874300")) == "$1.874.300"
    assert dinero(Decimal("3200000"), "+") == "+$3.200.000"
    assert dinero(Decimal("62000"), "-") == "−$62.000"
    assert dinero(Decimal("-5000"), "auto") == "−$5.000"
    assert dinero(Decimal("0.5")) == "$1"


def test_porcentaje_y_fecha():
    assert porcentaje(58.57) == "58,6 %"
    assert fecha_corta(date(2026, 10, 31)) == "31 oct"


def test_vista_resumen():
    r = obtener_resumen(1, 2026, 10)
    v = vista_resumen(r)

    assert v["queda"] == r.ingresos_mes - r.gastos_mes
    assert v["altura_ingresos"] == 200  # la mayor de las dos cápsulas llega al tope
    assert v["categorias"][0]["mayor"] and v["categorias"][0]["ancho"] == 100
    assert round(sum(c["pct"] for c in v["categorias"]), 6) == 100


def test_vista_resumen_sin_movimientos_no_divide_por_cero():
    r = obtener_resumen(1, 2026, 10).model_copy(
        update={"ingresos_mes": Decimal(0), "gastos_mes": Decimal(0), "gastos_por_categoria": []}
    )
    v = vista_resumen(r)

    assert v["pct_gastado"] == 0 and v["categorias"] == []


def test_resumen_y_movimientos_coinciden():
    from app.schemas.movimientos import MovimientoEntrada
    from app.services import movimientos

    nuevo = movimientos.crear(1, MovimientoEntrada(
        tipo="gasto", monto=Decimal("50000"), categoria_id=3, cuenta_id=1,
        fecha=date(2026, 10, 31), descripcion="Panadería"))
    resumen = obtener_resumen(1, 2026, 10)

    assert resumen.gastos_mes == movimientos.listar(1, 2026, 10).gastos == Decimal("1924300")
    assert resumen.movimientos_recientes[0].id == nuevo.id


def test_fecha_larga():
    from app.web.formato import fecha_larga

    assert fecha_larga(date(2026, 10, 31)) == "Sábado 31 de octubre"
    assert fecha_larga(date(2026, 11, 2)) == "Lunes 2 de noviembre"


def test_saldos_reales_y_deuda(monkeypatch):
    from app.services import movimientos
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 11, 15))

    r = obtener_resumen(1, 2026, 10)

    assert r.saldo_total == Decimal("4382900")
    assert r.deuda_tarjetas == Decimal("840000")
    assert [c.nombre for c in r.cuentas] == ["Cuenta de ahorros", "Billetera digital", "Efectivo"]
    assert r.cuentas[0].tipo == "Cuenta de ahorros"
