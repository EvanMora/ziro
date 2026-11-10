"""Presupuestos mensuales por categoría (ver app/schemas/presupuestos.py).

Fase 2. Falta lo que no se decidió aún, por ejemplo qué pasa con el presupuesto de una categoría
que se elimina: por ahora ese monto simplemente deja de mostrarse.

TODO(backend): tabla Presupuesto (id, usuario_id, categoria_id, monto_limite, mes, anio), ver
docs/alcance.md. Mientras tanto se guarda en memoria y se borra al reiniciar el servidor.
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from app.schemas.movimientos import ListaMovimientos
from app.schemas.presupuestos import (
    Estado,
    GastoDelDia,
    PresupuestoCategoria,
    PresupuestoDelMes,
    PresupuestoEntrada,
)
from app.services import categorias, movimientos
from app.services.comun import ErrorValidacion

MAX_MONTO = movimientos.MAX_MONTO

# (usuario_id, anio, mes) → {categoria_id: límite}
_presupuestos: dict[tuple[int, int, int], dict[int, Decimal]] = {}
_sembrados: set[tuple[int, int, int]] = set()

# Ejemplo para la demo: el mes anterior al actual ya trae presupuesto, con una categoría en
# alerta y otra excedida frente a la plantilla de movimientos (services/movimientos.py).
_EJEMPLO = {"Arriendo": "1100000", "Mercado": "450000", "Transporte": "300000", "Ocio": "150000"}


def reiniciar() -> None:
    """Vacía el almacén. Solo para tests."""
    _presupuestos.clear()
    _sembrados.clear()


def _mes_anterior(d: date) -> tuple[int, int]:
    return (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)


def _sembrar(usuario_id: int, anio: int, mes: int) -> None:
    clave = (usuario_id, anio, mes)
    if clave in _sembrados:
        return
    _sembrados.add(clave)
    if (anio, mes) == _mes_anterior(movimientos.hoy()) and clave not in _presupuestos:
        _presupuestos[clave] = {categorias.predeterminada(nombre).id: Decimal(monto)
                                for nombre, monto in _EJEMPLO.items()}


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
    return [GastoDelDia(fecha=d, total=totales[d], movimientos=cuantos[d])
            for d in (primero + timedelta(days=i) for i in range(ultimo))]


def gastos_del_mes(usuario_id: int, anio: int, mes: int, lista: ListaMovimientos | None = None) -> list:
    """Los movimientos de gasto del mes, del más reciente al más antiguo. lista: el mes ya listado
    con movimientos.listar (sin filtros), si la ruta lo tiene, para no recorrerlo otra vez."""
    lista = movimientos.listar(usuario_id, anio, mes) if lista is None else lista
    return [m for m in lista.movimientos if m.tipo == "gasto"]


def del_mes(usuario_id: int, anio: int, mes: int, gastos: list | None = None,
            lista_categorias: list | None = None) -> PresupuestoDelMes:
    """gastos (gastos_del_mes) y lista_categorias (categorias.listar): si la ruta ya los leyó, para
    no listar el mes ni leer las categorías dos veces en la misma petición."""
    _sembrar(usuario_id, anio, mes)
    limites = _presupuestos.get((usuario_id, anio, mes), {})
    gastos = gastos_del_mes(usuario_id, anio, mes) if gastos is None else gastos

    por_categoria: dict[int, Decimal] = defaultdict(Decimal)
    for m in gastos:
        por_categoria[m.categoria.id] += m.monto

    filas = []
    for c in categorias.listar(usuario_id) if lista_categorias is None else lista_categorias:
        if c.id not in limites:
            continue  # sin presupuesto, o la categoría ya no existe
        limite, gastado = limites[c.id], por_categoria[c.id]
        pct = _pct(gastado, limite)
        filas.append(PresupuestoCategoria(categoria=categorias.ref(c), limite=limite, gastado=gastado,
                                          restante=limite - gastado, pct=pct, estado=_estado(pct)))

    total = sum((f.limite for f in filas), Decimal(0))
    gastado = sum((f.gastado for f in filas), Decimal(0))
    con_presupuesto = {f.categoria.id for f in filas}
    pct = _pct(gastado, total)
    return PresupuestoDelMes(
        anio=anio, mes=mes, creado=bool(filas), categorias=filas, total=total, gastado=gastado,
        restante=total - gastado, pct=pct, estado=_estado(pct),
        sin_presupuesto=sum((m.monto for m in gastos if m.categoria.id not in con_presupuesto), Decimal(0)),
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

    # TODO(backend): en una transacción, DELETE de los presupuestos del mes e INSERT de los nuevos.
    _sembrados.add((usuario_id, anio, mes))
    _presupuestos[(usuario_id, anio, mes)] = limites
    return del_mes(usuario_id, anio, mes)
