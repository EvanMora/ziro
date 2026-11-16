"""Metas de ahorro: crear, editar y eliminar; aportar, retirar y borrar aportes; y el progreso de cada
meta (ver app/schemas/metas.py y docs/superpowers/specs/2026-11-16-metas-design.md).

Los aportes son plata apartada: no tocan el saldo de las cuentas ni los ingresos y gastos del mes.
Lo ahorrado es la suma de los aportes de la meta (los retiros van en negativo).
"""
from collections import defaultdict
from datetime import date
from decimal import ROUND_CEILING, Decimal

from sqlalchemy import delete, select, update

from app.models.metas import AporteMetaDB, MetaDB
from app.schemas.metas import (
    Aporte,
    AporteEntrada,
    EstadoMeta,
    Meta,
    MetaConProgreso,
    MetaEntrada,
    PanelMetas,
)
from app.services import database, movimientos
from app.services.comun import ErrorValidacion, NoEncontrado, limpiar_texto, normalizar
from app.web.formato import dinero, fecha_corta

MAX_NOMBRE = 40
MAX_METAS = 20  # por usuario
ANIOS_MAX = 50  # la fecha límite, como mucho dentro de 50 años


def _como_meta(fila: MetaDB) -> Meta:
    return Meta(id=fila.id, nombre=fila.nombre, objetivo=movimientos._normalizar_monto(fila.objetivo),
                fecha_limite=fila.fecha_limite, creada_en=fila.creada_en)


def _metas(usuario_id: int) -> list[Meta]:
    with database.sesion() as db:
        filas = db.execute(select(MetaDB).where(MetaDB.usuario_id == usuario_id).order_by(MetaDB.id)).scalars()
        return [_como_meta(f) for f in filas]


def _meta(usuario_id: int, id: int) -> Meta:
    with database.sesion() as db:
        fila = db.execute(select(MetaDB).where(MetaDB.id == id, MetaDB.usuario_id == usuario_id)).scalar_one_or_none()
        if fila is None:
            raise NoEncontrado(id)
        return _como_meta(fila)


def _aportes(usuario_id: int) -> dict[int, list[Aporte]]:
    """Los aportes de cada meta del usuario, del más nuevo al más viejo."""
    por_meta: dict[int, list[Aporte]] = defaultdict(list)
    with database.sesion() as db:
        filas = db.execute(
            select(AporteMetaDB).where(AporteMetaDB.usuario_id == usuario_id)
            .order_by(AporteMetaDB.fecha.desc(), AporteMetaDB.id.desc())
        ).scalars()
        for f in filas:
            por_meta[f.meta_id].append(Aporte(id=f.id, monto=movimientos._normalizar_monto(f.monto), fecha=f.fecha))
    return por_meta


def _ahorrado(aportes: list[Aporte]) -> Decimal:
    return movimientos._normalizar_monto(sum((a.monto for a in aportes), Decimal(0)))


# ---------- Progreso ----------

def _meses_restantes(hoy: date, limite: date) -> int:
    """Del mes actual al de la fecha límite, ambos incluidos."""
    return (limite.year - hoy.year) * 12 + limite.month - hoy.month + 1


def _estado(m: Meta, ahorrado: Decimal, hoy: date) -> EstadoMeta:
    if ahorrado >= m.objetivo:
        return "cumplida"
    if m.fecha_limite is None:
        return "sin_fecha"
    if m.fecha_limite < hoy:
        return "vencida"
    total = (m.fecha_limite - m.creada_en).days
    if total <= 0:
        return "al_dia"
    esperado = m.objetivo * Decimal((hoy - m.creada_en).days) / Decimal(total)
    return "atrasada" if ahorrado < esperado else "al_dia"


def _progreso(m: Meta, aportes: list[Aporte], hoy: date) -> MetaConProgreso:
    ahorrado = _ahorrado(aportes)
    faltante = max(m.objetivo - ahorrado, Decimal(0))
    estado = _estado(m, ahorrado, hoy)
    por_mes = meses = None
    if estado in ("al_dia", "atrasada"):
        meses = _meses_restantes(hoy, m.fecha_limite)
        por_mes = (faltante / meses).to_integral_value(rounding=ROUND_CEILING)
    pct = min(float(ahorrado / m.objetivo * 100), 100.0) if ahorrado > 0 else 0.0
    return MetaConProgreso(meta=m, ahorrado=ahorrado, faltante=movimientos._normalizar_monto(faltante), pct=pct,
                           estado=estado, por_mes=por_mes, meses_restantes=meses, aportes=aportes)


def panel(usuario_id: int) -> PanelMetas:
    hoy = movimientos.hoy()
    aportes = _aportes(usuario_id)
    lista = [_progreso(m, aportes.get(m.id, []), hoy) for m in _metas(usuario_id)]
    # Sin cumplir primero, por fecha límite (las sin fecha al final); después las cumplidas.
    lista.sort(key=lambda p: (p.estado == "cumplida", p.meta.fecha_limite is None,
                              p.meta.fecha_limite or date.max, p.meta.id))
    return PanelMetas(
        metas=lista,
        total_ahorrado=movimientos._normalizar_monto(sum((p.ahorrado for p in lista), Decimal(0))),
        total_objetivo=movimientos._normalizar_monto(sum((p.meta.objetivo for p in lista), Decimal(0))),
    )


# ---------- Crear, editar y eliminar ----------

def _validar(usuario_id: int, e: MetaEntrada, actual: Meta | None) -> str:
    """Devuelve el nombre limpio o lanza ErrorValidacion."""
    errores: dict[str, str] = {}
    hoy = movimientos.hoy()
    existentes = _metas(usuario_id)

    nombre = limpiar_texto(e.nombre)
    if not nombre:
        errores["nombre"] = "Escribe un nombre."
    elif len(nombre) > MAX_NOMBRE:
        errores["nombre"] = f"Máximo {MAX_NOMBRE} caracteres."
    elif any(normalizar(m.nombre) == normalizar(nombre) for m in existentes if actual is None or m.id != actual.id):
        errores["nombre"] = "Ya tienes una meta con ese nombre."

    if not e.objetivo.is_finite() or movimientos._normalizar_monto(e.objetivo) <= 0:
        errores["objetivo"] = "Escribe un objetivo mayor que 0."
    elif e.objetivo >= movimientos.MAX_MONTO:
        errores["objetivo"] = "El monto es demasiado grande."

    # Una fecha que ya tenía la meta se puede conservar aunque haya pasado; una nueva, no.
    cambia_fecha = actual is None or e.fecha_limite != actual.fecha_limite
    if e.fecha_limite is not None and cambia_fecha:
        if e.fecha_limite < hoy:
            errores["fecha_limite"] = "La fecha límite no puede ser pasada."
        elif e.fecha_limite.year > hoy.year + ANIOS_MAX:
            errores["fecha_limite"] = f"Elige una fecha de los próximos {ANIOS_MAX} años."

    if actual is None and not errores and len(existentes) >= MAX_METAS:
        errores["general"] = f"Llegaste al máximo de {MAX_METAS} metas."
    if errores:
        raise ErrorValidacion(errores)
    return nombre


def crear(usuario_id: int, e: MetaEntrada) -> Meta:
    nombre = _validar(usuario_id, e, None)
    with database.sesion() as db:
        fila = MetaDB(usuario_id=usuario_id, nombre=nombre, objetivo=movimientos._normalizar_monto(e.objetivo),
                      fecha_limite=e.fecha_limite, creada_en=movimientos.hoy())
        db.add(fila)
        db.flush()
        return _como_meta(fila)


def actualizar(usuario_id: int, id: int, e: MetaEntrada) -> Meta:
    actual = _meta(usuario_id, id)
    nombre = _validar(usuario_id, e, actual)
    objetivo = movimientos._normalizar_monto(e.objetivo)
    with database.sesion() as db:
        db.execute(update(MetaDB).where(MetaDB.id == id, MetaDB.usuario_id == usuario_id)
                   .values(nombre=nombre, objetivo=objetivo, fecha_limite=e.fecha_limite))
    return actual.model_copy(update={"nombre": nombre, "objetivo": objetivo, "fecha_limite": e.fecha_limite})


def eliminar(usuario_id: int, id: int) -> None:
    """Borra la meta y sus aportes, en una sola transacción."""
    _meta(usuario_id, id)
    with database.sesion() as db:
        db.execute(delete(AporteMetaDB).where(AporteMetaDB.meta_id == id, AporteMetaDB.usuario_id == usuario_id))
        db.execute(delete(MetaDB).where(MetaDB.id == id, MetaDB.usuario_id == usuario_id))


# ---------- Aportes y retiros ----------

def aportar(usuario_id: int, meta_id: int, e: AporteEntrada) -> Aporte:
    """Registra un aporte, o un retiro si e.retiro (no más de lo ahorrado)."""
    m = _meta(usuario_id, meta_id)
    hoy = movimientos.hoy()
    errores: dict[str, str] = {}
    if not e.monto.is_finite() or movimientos._normalizar_monto(e.monto) <= 0:
        errores["monto"] = "Escribe un monto mayor que 0."
    elif e.monto >= movimientos.MAX_MONTO:
        errores["monto"] = "El monto es demasiado grande."
    elif e.retiro:
        ahorrado = _ahorrado(_aportes(usuario_id).get(meta_id, []))
        if movimientos._normalizar_monto(e.monto) > ahorrado:
            errores["monto"] = f"Solo tienes {dinero(ahorrado)} ahorrados en esta meta."
    if e.fecha > hoy:
        errores["fecha"] = "La fecha no puede ser futura."
    elif e.fecha < m.creada_en:
        errores["fecha"] = f"La meta se creó el {fecha_corta(m.creada_en)}: elige esa fecha o una posterior."
    if errores:
        raise ErrorValidacion(errores)

    monto = movimientos._normalizar_monto(e.monto)
    with database.sesion() as db:
        fila = AporteMetaDB(usuario_id=usuario_id, meta_id=meta_id, monto=-monto if e.retiro else monto, fecha=e.fecha)
        db.add(fila)
        db.flush()
        return Aporte(id=fila.id, monto=movimientos._normalizar_monto(fila.monto), fecha=fila.fecha)


def eliminar_aporte(usuario_id: int, meta_id: int, aporte_id: int) -> None:
    """Borra un aporte o un retiro de la meta, salvo que lo ahorrado quede en negativo."""
    _meta(usuario_id, meta_id)
    aportes = _aportes(usuario_id).get(meta_id, [])
    aporte = next((a for a in aportes if a.id == aporte_id), None)
    if aporte is None:
        raise NoEncontrado(aporte_id)
    if _ahorrado(aportes) - aporte.monto < 0:
        raise ErrorValidacion({"general": "Si lo borras, lo ahorrado quedaría en negativo. Borra primero el retiro."})
    with database.sesion() as db:
        db.execute(delete(AporteMetaDB).where(AporteMetaDB.id == aporte_id, AporteMetaDB.usuario_id == usuario_id))
