"""Categorías: las predeterminadas del sistema y las propias de cada usuario.

Reglas (docs/alcance.md y app/schemas/categorias.py):
- Las predeterminadas no se editan ni se eliminan.
- El nombre es obligatorio, de hasta MAX_NOMBRE caracteres y único dentro del tipo (sin distinguir
  tildes ni mayúsculas). "Mercado" puede existir como gasto y como ingreso.
- El tipo solo cambia mientras la categoría no tenga movimientos: si los tiene, un gasto quedaría
  con una categoría de ingreso.
- Eliminar una categoría con movimientos exige pasarlos antes a otra del mismo tipo (mover_a). El
  alcance dejaba "bloquear o reasignar" por decidir: así no se pierde ningún movimiento y tampoco
  hace falta borrarlos uno por uno.

Las predeterminadas (usuario_id NULL) las siembra app/services/database.py al crear el esquema;
las propias viven en la tabla `categorias` con su dueño. Las firmas y los modelos se mantienen.

services/movimientos.py importa este módulo para validar la categoría de cada movimiento. Las
funciones de aquí que necesitan los movimientos lo importan adentro para no formar un ciclo.
"""
from decimal import Decimal

from sqlalchemy import delete, select, update

from app.models.categorias import CategoriaDB
from app.schemas.categorias import (
    Categoria,
    CategoriaDelMes,
    CategoriaEntrada,
    CategoriasDelMes,
)
from app.schemas.movimientos import CategoriaRef
from app.services import database
from app.services.comun import (
    ErrorValidacion,
    NoEncontrado,
    NoPermitido,
    limpiar_texto,
    normalizar,
)

MAX_NOMBRE = 40
MAX_PROPIAS = 50  # por usuario


def reiniciar() -> None:
    """Vacía la tabla (y vuelve a sembrar las predeterminadas). Solo para tests."""
    database.reiniciar()


def ref(categoria: Categoria) -> CategoriaRef:
    """La forma que llevan los movimientos."""
    return CategoriaRef(id=categoria.id, nombre=categoria.nombre, tipo=categoria.tipo)


def _como_categoria(fila: CategoriaDB) -> Categoria:
    return Categoria(
        id=fila.id, nombre=fila.nombre, tipo=fila.tipo, predeterminada=fila.usuario_id is None,
    )


def predeterminada(nombre: str) -> Categoria:
    with database.sesion() as db:
        fila = db.execute(
            select(CategoriaDB).where(CategoriaDB.usuario_id.is_(None), CategoriaDB.nombre == nombre)
        ).scalar_one()
        return _como_categoria(fila)


def _de_usuario(usuario_id: int) -> list[Categoria]:
    with database.sesion() as db:
        filas = db.execute(
            select(CategoriaDB).where(CategoriaDB.usuario_id == usuario_id).order_by(CategoriaDB.id)
        ).scalars().all()
        return [_como_categoria(f) for f in filas]


def listar(usuario_id: int) -> list[Categoria]:
    """Primero las predeterminadas y luego las propias, en el orden en que se crearon."""
    with database.sesion() as db:
        filas = db.execute(
            select(CategoriaDB)
            .where(CategoriaDB.usuario_id.is_(None) | (CategoriaDB.usuario_id == usuario_id))
            # False (NULL) primero: las predeterminadas van antes que las propias.
            .order_by(CategoriaDB.usuario_id.is_not(None), CategoriaDB.id)
        ).scalars().all()
        return [_como_categoria(f) for f in filas]


def obtener(usuario_id: int, id: int) -> Categoria | None:
    with database.sesion() as db:
        fila = db.execute(
            select(CategoriaDB).where(
                CategoriaDB.id == id,
                CategoriaDB.usuario_id.is_(None) | (CategoriaDB.usuario_id == usuario_id),
            )
        ).scalar_one_or_none()
        return _como_categoria(fila) if fila is not None else None


def _propia(usuario_id: int, id: int) -> Categoria:
    categoria = obtener(usuario_id, id)
    if categoria is None:
        raise NoEncontrado(id)
    if categoria.predeterminada:
        raise NoPermitido(id)
    return categoria


def _usos(usuario_id: int, id: int) -> int:
    from app.services import movimientos
    return movimientos.usos_por_categoria(usuario_id).get(id, 0)


def _nombre_de_tipo(tipo: str) -> str:
    return "ingresos" if tipo == "ingreso" else "gastos"


def _validar(usuario_id: int, entrada: CategoriaEntrada, actual: Categoria | None) -> str:
    """Devuelve el nombre limpio (sin espacios de sobra) o lanza ErrorValidacion."""
    errores: dict[str, str] = {}
    nombre = limpiar_texto(entrada.nombre)
    if not nombre:
        errores["nombre"] = "Escribe un nombre."
    elif len(nombre) > MAX_NOMBRE:
        errores["nombre"] = f"Máximo {MAX_NOMBRE} caracteres."
    elif any(normalizar(c.nombre) == normalizar(nombre) and c.tipo == entrada.tipo
             for c in listar(usuario_id) if actual is None or c.id != actual.id):
        errores["nombre"] = f"Ya hay una categoría de {_nombre_de_tipo(entrada.tipo)} con ese nombre."
    if actual is None and len(_de_usuario(usuario_id)) >= MAX_PROPIAS:
        errores["general"] = f"Llegaste al máximo de {MAX_PROPIAS} categorías propias."
    if actual is not None and entrada.tipo != actual.tipo and _usos(usuario_id, actual.id):
        errores["tipo"] = "Ya tiene movimientos: el tipo no se puede cambiar."
    if errores:
        raise ErrorValidacion(errores)
    return nombre


def crear(usuario_id: int, entrada: CategoriaEntrada) -> Categoria:
    nombre = _validar(usuario_id, entrada, None)
    with database.sesion() as db:
        fila = CategoriaDB(usuario_id=usuario_id, nombre=nombre, tipo=entrada.tipo)
        db.add(fila)
        db.flush()
        return _como_categoria(fila)


def actualizar(usuario_id: int, id: int, entrada: CategoriaEntrada) -> Categoria:
    actual = _propia(usuario_id, id)
    nombre = _validar(usuario_id, entrada, actual)
    with database.sesion() as db:
        db.execute(
            update(CategoriaDB)
            .where(CategoriaDB.id == id, CategoriaDB.usuario_id == usuario_id)
            .values(nombre=nombre, tipo=entrada.tipo)
        )
    return Categoria(id=id, nombre=nombre, tipo=entrada.tipo, predeterminada=False)


def eliminar(usuario_id: int, id: int, mover_a: int | None = None) -> None:
    """Si la categoría tiene movimientos, mover_a es la categoría (del mismo tipo) que los recibe."""
    from app.models.movimientos import MovimientoDB
    categoria = _propia(usuario_id, id)
    usos = _usos(usuario_id, id)
    if usos:
        destino = obtener(usuario_id, mover_a) if mover_a is not None else None
        if mover_a is None:
            plural = "movimiento" if usos == 1 else "movimientos"
            raise ErrorValidacion({"mover_a": f"Tiene {usos} {plural}. Elige a qué categoría pasarlos."})
        if destino is None or destino.id == id:
            raise ErrorValidacion({"mover_a": "Elige otra categoría."})
        if destino.tipo != categoria.tipo:
            raise ErrorValidacion({"mover_a": f"Elige una categoría de {_nombre_de_tipo(categoria.tipo)}."})
        # Reasignar y borrar en la misma transacción: no se pierde ningún movimiento.
        with database.sesion() as db:
            db.execute(
                update(MovimientoDB)
                .where(MovimientoDB.categoria_id == id,
                       MovimientoDB.usuario_id == usuario_id)
                .values(categoria_id=mover_a)
            )
            db.execute(
                delete(CategoriaDB).where(CategoriaDB.id == id, CategoriaDB.usuario_id == usuario_id)
            )
    else:
        with database.sesion() as db:
            db.execute(
                delete(CategoriaDB).where(CategoriaDB.id == id, CategoriaDB.usuario_id == usuario_id)
            )


def del_mes(usuario_id: int, anio: int, mes: int) -> CategoriasDelMes:
    """Cada categoría con lo que sumó en el mes, separadas en gastos e ingresos."""
    from app.services import movimientos
    lista = movimientos.listar(usuario_id, anio, mes)
    usos = movimientos.usos_por_categoria(usuario_id)
    totales: dict[int, Decimal] = {}
    cuantos: dict[int, int] = {}
    for m in lista.movimientos:
        totales[m.categoria.id] = totales.get(m.categoria.id, Decimal(0)) + m.monto
        cuantos[m.categoria.id] = cuantos.get(m.categoria.id, 0) + 1

    filas = [
        CategoriaDelMes(categoria=c, total=totales.get(c.id, Decimal(0)), movimientos=cuantos.get(c.id, 0),
                        usos=usos.get(c.id, 0))
        for c in listar(usuario_id)
    ]
    # sorted() es estable: con el mismo total se conserva el orden del catálogo.
    filas.sort(key=lambda f: f.total, reverse=True)
    return CategoriasDelMes(
        anio=anio,
        mes=mes,
        gastos=[f for f in filas if f.categoria.tipo == "gasto"],
        ingresos=[f for f in filas if f.categoria.tipo == "ingreso"],
        total_gastos=lista.gastos,
        total_ingresos=lista.ingresos,
    )
