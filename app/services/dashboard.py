"""Datos de la pantalla de Resumen.

Ingresos, gastos, categorías y recientes salen de services/movimientos.py, así el Resumen y la
sección Movimientos siempre muestran las mismas cifras. Los saldos y la deuda de las tarjetas
salen de services/cuentas.py, igual que en la sección Cuentas. Los pagos de tarjeta no son
movimientos: no aparecen en los ingresos, los gastos ni los recientes.
"""
from decimal import Decimal

from app.schemas.dashboard import CuentaSaldo, GastoCategoria, ResumenDashboard
from app.schemas.cuentas import NOMBRE_TIPO, Cuenta
from app.schemas.movimientos import ListaMovimientos
from app.services import cuentas as cuentas_servicio
from app.services import movimientos

CANTIDAD_RECIENTES = 4


def obtener_resumen(usuario_id: int, anio: int, mes: int, lista: ListaMovimientos | None = None,
                    lista_cuentas: list[Cuenta] | None = None) -> ResumenDashboard:
    """lista (movimientos.listar del mes, sin filtros) y lista_cuentas (cuentas.listar): si la ruta
    ya los leyó, para no recorrer el mes ni leer las cuentas otra vez en la misma petición."""
    lista = movimientos.listar(usuario_id, anio, mes) if lista is None else lista

    gastos: dict[str, Decimal] = {}
    for m in lista.movimientos:
        if m.tipo == "gasto":
            gastos[m.categoria.nombre] = gastos.get(m.categoria.nombre, Decimal(0)) + m.monto

    # Solo los saldos: el Resumen no usa los movimientos y pagos por cuenta que cuenta panel().
    # Las sumas son las mismas que panel().tienes y panel().debes.
    lista_cuentas = cuentas_servicio.listar(usuario_id) if lista_cuentas is None else lista_cuentas
    saldos = cuentas_servicio.saldos(usuario_id, lista_cuentas)
    cuentas = [CuentaSaldo(nombre=c.nombre, tipo=NOMBRE_TIPO[c.tipo], saldo=saldos[c.id])
               for c in lista_cuentas if not cuentas_servicio.es_tarjeta(c.tipo)]
    deuda = sum((saldos[c.id] for c in lista_cuentas if cuentas_servicio.es_tarjeta(c.tipo)), Decimal(0))

    return ResumenDashboard(
        anio=anio,
        mes=mes,
        saldo_total=sum((c.saldo for c in cuentas), Decimal(0)),
        cuentas=cuentas,
        deuda_tarjetas=deuda,
        ingresos_mes=lista.ingresos,
        gastos_mes=lista.gastos,
        gastos_por_categoria=[
            GastoCategoria(categoria=c, total=t) for c, t in sorted(gastos.items(), key=lambda par: par[1], reverse=True)
        ],
        movimientos_recientes=lista.movimientos[:CANTIDAD_RECIENTES],
    )
