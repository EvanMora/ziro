"""Datos de la pantalla de Resumen.

Ingresos, gastos, categorías y recientes salen de services/movimientos.py, así el Resumen y la
sección Movimientos siempre muestran las mismas cifras. Los saldos y la deuda de las tarjetas
salen de services/cuentas.py, igual que en la sección Cuentas. Los pagos de tarjeta no son
movimientos: no aparecen en los ingresos, los gastos ni los recientes.
"""
from decimal import Decimal

from app.schemas.cuentas import NOMBRE_TIPO
from app.schemas.dashboard import CuentaSaldo, GastoCategoria, ResumenDashboard
from app.services import cuentas as cuentas_servicio
from app.services import movimientos

CANTIDAD_RECIENTES = 4


def obtener_resumen(usuario_id: int, anio: int, mes: int) -> ResumenDashboard:
    lista = movimientos.listar(usuario_id, anio, mes)

    gastos: dict[str, Decimal] = {}
    for m in lista.movimientos:
        if m.tipo == "gasto":
            gastos[m.categoria.nombre] = gastos.get(m.categoria.nombre, Decimal(0)) + m.monto

    panel = cuentas_servicio.panel(usuario_id)
    cuentas = [CuentaSaldo(nombre=c.cuenta.nombre, tipo=NOMBRE_TIPO[c.cuenta.tipo], saldo=c.saldo)
               for c in panel.dinero]

    return ResumenDashboard(
        anio=anio,
        mes=mes,
        saldo_total=panel.tienes,
        cuentas=cuentas,
        deuda_tarjetas=panel.debes,
        ingresos_mes=lista.ingresos,
        gastos_mes=lista.gastos,
        gastos_por_categoria=[
            GastoCategoria(categoria=c, total=t) for c, t in sorted(gastos.items(), key=lambda par: par[1], reverse=True)
        ],
        movimientos_recientes=lista.movimientos[:CANTIDAD_RECIENTES],
    )
