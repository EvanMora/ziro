"""Presupuestos mensuales por categoría (ver app/schemas/presupuestos.py).

Fase 2.

Los límites viven en la tabla `presupuestos` (app/models/presupuestos.py): una fila por
usuario, mes y categoría de gasto, con unicidad uq_presupuesto_mes. Crear o reemplazar el
presupuesto de un mes es un DELETE del mes y un INSERT de los nuevos, en una sola transacción.
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete, select

from app.models.presupuestos import PresupuestoDB
from app.schemas.movimientos import ListaMovimientos
from app.schemas.presupuestos import (
    Estado,
    GastoDelDia,
    PresupuestoCategoria,
    PresupuestoDelMes,
    PresupuestoEntrada,
)
from app.services import categorias, database, movimientos
from app.services.comun import ErrorValidacion

MAX_MONTO = movimientos.MAX_MONTO

def reiniciar() -> None:
    """Vacía la base (y vuelve a sembrar las categorías predeterminadas). Solo para tests."""
    database.reiniciar()


def _mes_anterior(d: date) -> tuple[int, int]:
    return (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)


def _estado(pct: float) -> Estado:
    if pct > 100:
        return "excedido"
    return "alerta" if pct >= 80 else "ok"


def _pct(gastado: Decimal, limite: Decimal) -> float:
    return float(gastado / limite * 100) if limite > 0 else 0.0


def _dias(lista, anio: int, mes: int) -> list[GastoDelDia]:
    totales: dict[date, Decimal] = defaultdict(Decimal)
    cuantos: dict[date, int] = defaultdict(int)
    for m in lista:
        totales[m.fecha] += m.monto
        cuantos[m.fecha] += 1
    primero = date(anio, mes, 1)
    ultimo = movimientos._ultimo_dia(anio, mes)
    return [GastoDelDia(fecha=d, total=movimientos._normalizar_monto(totales[d]), movimientos=cuantos[d])
            for d in (primero + timedelta(days=i) for i in range(ultimo))]


def gastos_del_mes(usuario_id: int, anio: int, mes: int, lista: ListaMovimientos | None = None) -> list:
    """Los movimientos de gasto del mes, del más reciente al más antiguo. lista: el mes ya listado
    con movimientos.listar (sin filtros), si la ruta lo tiene, para no recorrerlo otra vez."""
    lista = movimientos.listar(usuario_id, anio, mes) if lista is None else lista
    return [m for m in lista.movimientos if m.tipo == "gasto"]


def _limites(usuario_id: int, anio: int, mes: int) -> dict[int, Decimal]:
    from app.services.movimientos import _normalizar_monto
    with database.sesion() as db:
        filas = db.execute(
            select(PresupuestoDB.categoria_id, PresupuestoDB.monto_limite)
            .where(PresupuestoDB.usuario_id == usuario_id,
                   PresupuestoDB.anio == anio, PresupuestoDB.mes == mes)
        ).all()
        return {categoria_id: _normalizar_monto(monto) for categoria_id, monto in filas}


def del_mes(usuario_id: int, anio: int, mes: int, gastos: list | None = None,
            lista_categorias: list | None = None) -> PresupuestoDelMes:
    """gastos (gastos_del_mes) y lista_categorias (categorias.listar): si la ruta ya los leyó, para
    no listar el mes ni leer las categorías dos veces en la misma petición."""
    limites = _limites(usuario_id, anio, mes)
    gastos = gastos_del_mes(usuario_id, anio, mes) if gastos is None else gastos

    por_categoria: dict[int, Decimal] = defaultdict(Decimal)
    for m in gastos:
        por_categoria[m.categoria.id] += m.monto

    filas = []
    _nm = movimientos._normalizar_monto
    for c in categorias.listar(usuario_id) if lista_categorias is None else lista_categorias:
        if c.id not in limites:
            continue  # sin presupuesto, o la categoría ya no existe
        limite, gastado = limites[c.id], _nm(por_categoria[c.id])
        pct = _pct(gastado, limite)
        filas.append(PresupuestoCategoria(categoria=categorias.ref(c), limite=limite, gastado=gastado,
                                          restante=_nm(limite - gastado), pct=pct, estado=_estado(pct)))

    total = _nm(sum((f.limite for f in filas), Decimal(0)))
    gastado = _nm(sum((f.gastado for f in filas), Decimal(0)))
    con_presupuesto = {f.categoria.id for f in filas}
    pct = _pct(gastado, total)
    return PresupuestoDelMes(
        anio=anio, mes=mes, creado=bool(filas), categorias=filas, total=total, gastado=gastado,
        restante=_nm(total - gastado), pct=pct, estado=_estado(pct),
        sin_presupuesto=_nm(sum((m.monto for m in gastos if m.categoria.id not in con_presupuesto), Decimal(0))),
        dias=_dias(gastos, anio, mes),
    )


def guardar(usuario_id: int, anio: int, mes: int, entrada: PresupuestoEntrada) -> PresupuestoDelMes:
    """Crea o reemplaza el presupuesto del mes. Errores por campo: "monto_<categoria_id>" y "general"."""
    hoy = movimientos.hoy()
    errores: dict[str, str] = {}
    if (anio, mes) > (hoy.year, hoy.month):
        errores["general"] = "Solo puedes hacer el presupuesto del mes actual o de meses pasados."

    de_gasto = {c.id for c in categorias.listar(usuario_id) if c.tipo == "gasto"}
    limites: dict[int, Decimal] = {}
    for item in entrada.montos:
        campo = f"monto_{item.categoria_id}"
        if item.categoria_id not in de_gasto:
            errores["general"] = "Una de las categorías ya no existe o no es de gasto. Recarga la página."
            continue
        if item.categoria_id in limites:
            errores[campo] = "Esta categoría está repetida."
            continue
        monto = item.monto
        if not monto.is_finite() or monto < 0:
            errores[campo] = "Escribe un monto de 0 o más."
        elif monto >= MAX_MONTO:
            errores[campo] = "El monto es demasiado grande."
        elif monto.quantize(Decimal(1)) > 0:
            limites[item.categoria_id] = monto.quantize(Decimal(1))

    if not limites and not errores:
        errores["general"] = "Ponle un monto al menos a una categoría."
    if errores:
        raise ErrorValidacion(errores)

    # Reemplazar el mes: borrar e insertar, en una sola transacción.
    with database.sesion() as db:
        db.execute(
            delete(PresupuestoDB).where(PresupuestoDB.usuario_id == usuario_id,
                                        PresupuestoDB.anio == anio, PresupuestoDB.mes == mes)
        )
        for categoria_id, monto in limites.items():
            db.add(PresupuestoDB(usuario_id=usuario_id, categoria_id=categoria_id,
                                 anio=anio, mes=mes, monto_limite=monto))
    return del_mes(usuario_id, anio, mes)
