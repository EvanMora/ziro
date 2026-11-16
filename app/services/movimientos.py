"""Movimientos: listar con filtros, crear, editar y eliminar.

Guardados en la tabla `movimientos` (modelo app/models/movimientos.py), filtrados por usuario_id.
Las firmas, los modelos de app/schemas/movimientos.py y las reglas de _validar() se mantienen.

La app no siembra movimientos: cada usuario solo ve los que registró (los datos de prueba de los
tests están en tests/plantilla.py).
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select, update

from app.models.categorias import CategoriaDB
from app.models.cuentas import CuentaDB
from app.models.movimientos import MovimientoDB
from app.schemas.movimientos import (
    CategoriaRef,
    CuentaRef,
    FiltrosMovimientos,
    ListaMovimientos,
    Movimiento,
    MovimientoEntrada,
)
from app.services import categorias, cuentas
from app.services import database
from app.services.comun import (  # la API los toma de aquí: servicio.ErrorValidacion
    ErrorValidacion,
    NoEncontrado,
    limpiar_texto,
)
from app.services.comun import normalizar as _normalizar

MAX_DESCRIPCION = 80
# Tope del monto: 12 dígitos enteros, los mismos que acepta el campo del diálogo. Sin tope, un
# monto como 1E+30 no cabe en la precisión de Decimal y rompe el formato de toda la pantalla.
MAX_MONTO = Decimal("1000000000000")

# Las cuentas salen de services/cuentas.py y las categorías de services/categorias.py.

def hoy() -> date:
    return date.today()


def reiniciar() -> None:
    """Vacía la base (y vuelve a sembrar las categorías predeterminadas). Solo para tests."""
    database.reiniciar()


def _ultimo_dia(anio: int, mes: int) -> int:
    siguiente = date(anio + mes // 12, mes % 12 + 1, 1)
    return (siguiente - date(anio, mes, 1)).days


def _como_movimiento(fila: MovimientoDB, nombre_categoria: str, tipo_categoria: str, nombre_cuenta: str) -> Movimiento:
    return Movimiento(
        id=fila.id, fecha=fila.fecha, descripcion=fila.descripcion,
        categoria=CategoriaRef(id=fila.categoria_id, nombre=nombre_categoria, tipo=tipo_categoria),
        cuenta=CuentaRef(id=fila.cuenta_id, nombre=nombre_cuenta),
        tipo=fila.tipo, monto=_normalizar_monto(fila.monto),
    )


def _columnas():
    """El movimiento con los nombres y el tipo de su categoría y cuenta, para armar el
    Movimiento del contrato sin una consulta por fila."""
    return (
        select(MovimientoDB, CategoriaDB.nombre, CategoriaDB.tipo, CuentaDB.nombre)
        .join(CategoriaDB, MovimientoDB.categoria_id == CategoriaDB.id)
        .join(CuentaDB, MovimientoDB.cuenta_id == CuentaDB.id)
    )


def _coincide(m: Movimiento, f: FiltrosMovimientos, buscar: str) -> bool:
    if f.tipo and m.tipo != f.tipo:
        return False
    if f.cuenta_id and m.cuenta.id != f.cuenta_id:
        return False
    if f.categoria_id and m.categoria.id != f.categoria_id:
        return False
    if buscar and not any(buscar in _normalizar(texto) for texto in (m.descripcion, m.categoria.nombre, m.cuenta.nombre)):
        return False
    return True


def catalogo(usuario_id: int) -> tuple[list[CuentaRef], list[CategoriaRef]]:
    return ([cuentas.ref(c) for c in cuentas.listar(usuario_id)],
            [categorias.ref(c) for c in categorias.listar(usuario_id)])


def desde(usuario_id: int, fecha: date) -> list[Movimiento]:
    """Los movimientos con fecha >= fecha, del más viejo al más nuevo."""
    with database.sesion() as db:
        filas = db.execute(
            _columnas().where(MovimientoDB.usuario_id == usuario_id, MovimientoDB.fecha >= fecha)
            .order_by(MovimientoDB.fecha, MovimientoDB.id)
        ).all()
        return [_como_movimiento(*f) for f in filas]


def usos_por_cuenta(usuario_id: int) -> dict[int, int]:
    """Cuántos movimientos tiene cada cuenta."""
    with database.sesion() as db:
        pares = db.execute(
            select(MovimientoDB.cuenta_id, func.count(MovimientoDB.id))
            .where(MovimientoDB.usuario_id == usuario_id)
            .group_by(MovimientoDB.cuenta_id)
        ).all()
        return {cuenta_id: cuantos for cuenta_id, cuantos in pares}


def usos_por_categoria(usuario_id: int) -> dict[int, int]:
    """Cuántos movimientos tiene cada categoría, contando todos los meses."""
    with database.sesion() as db:
        pares = db.execute(
            select(MovimientoDB.categoria_id, func.count(MovimientoDB.id))
            .where(MovimientoDB.usuario_id == usuario_id)
            .group_by(MovimientoDB.categoria_id)
        ).all()
        return {categoria_id: cuantos for categoria_id, cuantos in pares}


def listar(usuario_id: int, anio: int, mes: int, filtros: FiltrosMovimientos | None = None) -> ListaMovimientos:
    filtros = filtros or FiltrosMovimientos()
    primero = date(anio, mes, 1)
    ultimo = date(anio + mes // 12, mes % 12 + 1, 1)
    with database.sesion() as db:
        filas = db.execute(
            _columnas().where(MovimientoDB.usuario_id == usuario_id,
                              MovimientoDB.fecha >= primero, MovimientoDB.fecha < ultimo)
            .order_by(MovimientoDB.fecha.desc(), MovimientoDB.id.desc())
        ).all()
        movimientos = [_como_movimiento(*f) for f in filas]
    buscar = _normalizar((filtros.q or "").strip())
    encontrados = [m for m in movimientos if _coincide(m, filtros, buscar)]
    return ListaMovimientos(
        anio=anio,
        mes=mes,
        filtros=filtros,
        movimientos=encontrados,
        ingresos=_normalizar_monto(sum((m.monto for m in encontrados if m.tipo == "ingreso"), Decimal(0))),
        gastos=_normalizar_monto(sum((m.monto for m in encontrados if m.tipo == "gasto"), Decimal(0))),
    )


def obtener(usuario_id: int, id: int) -> Movimiento | None:
    with database.sesion() as db:
        fila = db.execute(
            _columnas().where(MovimientoDB.id == id, MovimientoDB.usuario_id == usuario_id)
        ).first()
        return _como_movimiento(*fila) if fila is not None else None


def _normalizar_monto(monto: Decimal) -> Decimal:
    """Sin exponente ("1E+5" → 100000) y con a lo sumo 2 decimales."""
    return monto.quantize(Decimal(1)) if monto == monto.to_integral_value() else monto.quantize(Decimal("0.01"))


def _validar(usuario_id: int, entrada: MovimientoEntrada) -> tuple[CategoriaRef, CuentaRef, str]:
    errores: dict[str, str] = {}
    if not entrada.monto.is_finite() or entrada.monto <= 0:
        errores["monto"] = "Escribe un monto mayor que 0."
    elif entrada.monto >= MAX_MONTO:
        errores["monto"] = "El monto es demasiado grande."
    encontrada = categorias.obtener(usuario_id, entrada.categoria_id)
    categoria = categorias.ref(encontrada) if encontrada else None
    if categoria is None:
        errores["categoria_id"] = "Elige una categoría."
    elif categoria.tipo != entrada.tipo:
        errores["categoria_id"] = f"Esa categoría es de {'ingresos' if categoria.tipo == 'ingreso' else 'gastos'}."
    encontrada_cuenta = cuentas.obtener(usuario_id, entrada.cuenta_id)
    cuenta = cuentas.ref(encontrada_cuenta) if encontrada_cuenta else None
    if cuenta is None:
        errores["cuenta_id"] = "Elige una cuenta."
    if entrada.fecha > hoy():
        errores["fecha"] = "La fecha no puede ser futura."
    descripcion = limpiar_texto(entrada.descripcion)
    if len(descripcion) > MAX_DESCRIPCION:
        errores["descripcion"] = f"Máximo {MAX_DESCRIPCION} caracteres."
    if errores:
        raise ErrorValidacion(errores)
    return categoria, cuenta, descripcion


def _guardar(usuario_id: int, id: int, entrada: MovimientoEntrada) -> Movimiento:
    categoria, cuenta, descripcion = _validar(usuario_id, entrada)
    monto = _normalizar_monto(entrada.monto)
    with database.sesion() as db:
        if id is None:
            fila = MovimientoDB(usuario_id=usuario_id, cuenta_id=cuenta.id, categoria_id=categoria.id,
                                tipo=entrada.tipo, monto=monto, fecha=entrada.fecha,
                                descripcion=descripcion)
            db.add(fila)
            db.flush()
            id = fila.id
        else:
            db.execute(
                update(MovimientoDB)
                .where(MovimientoDB.id == id, MovimientoDB.usuario_id == usuario_id)
                .values(cuenta_id=cuenta.id, categoria_id=categoria.id, tipo=entrada.tipo,
                        monto=monto, fecha=entrada.fecha, descripcion=descripcion)
            )
    return Movimiento(id=id, fecha=entrada.fecha, descripcion=descripcion,
                      categoria=categoria, cuenta=cuenta, tipo=entrada.tipo, monto=monto)


def crear(usuario_id: int, entrada: MovimientoEntrada) -> Movimiento:
    # El id lo pone la secuencia de la tabla; None lo señala en _guardar.
    return _guardar(usuario_id, None, entrada)


def actualizar(usuario_id: int, id: int, entrada: MovimientoEntrada) -> Movimiento:
    with database.sesion() as db:
        existe = db.execute(
            select(MovimientoDB.id).where(MovimientoDB.id == id, MovimientoDB.usuario_id == usuario_id)
        ).scalar_one_or_none()
        if existe is None:
            raise NoEncontrado(id)
    return _guardar(usuario_id, id, entrada)


def eliminar(usuario_id: int, id: int) -> None:
    with database.sesion() as db:
        borradas = db.execute(
            delete(MovimientoDB).where(MovimientoDB.id == id, MovimientoDB.usuario_id == usuario_id)
        ).rowcount
        if not borradas:
            raise NoEncontrado(id)
