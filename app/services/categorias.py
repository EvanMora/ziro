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

Por ahora las propias viven en memoria del proceso, como los movimientos.
TODO(backend): tabla Categoria con usuario_id (null en las predeterminadas). Las firmas y los
modelos se mantienen; usos y cambiar_categoria() pasan a ser un COUNT y un UPDATE de movimientos.

services/movimientos.py importa este módulo para validar la categoría de cada movimiento. Las
funciones de aquí que necesitan los movimientos lo importan adentro para no formar un ciclo.
"""
from decimal import Decimal

from app.schemas.categorias import (
    Categoria,
    CategoriaDelMes,
    CategoriaEntrada,
    CategoriasDelMes,
)
from app.schemas.movimientos import CategoriaRef
from app.services.comun import (
    ErrorValidacion,
    NoEncontrado,
    NoPermitido,
    limpiar_texto,
    normalizar,
)

MAX_NOMBRE = 40
MAX_PROPIAS = 50  # por usuario

_PREDETERMINADAS = [
    Categoria(id=1, nombre="Salario", tipo="ingreso", predeterminada=True),
    Categoria(id=2, nombre="Otros ingresos", tipo="ingreso", predeterminada=True),
    Categoria(id=3, nombre="Mercado", tipo="gasto", predeterminada=True),
    Categoria(id=4, nombre="Transporte", tipo="gasto", predeterminada=True),
    Categoria(id=5, nombre="Arriendo", tipo="gasto", predeterminada=True),
    Categoria(id=6, nombre="Ocio", tipo="gasto", predeterminada=True),
    Categoria(id=7, nombre="Otros gastos", tipo="gasto", predeterminada=True),
]
_PRIMER_ID_PROPIO = 100

_propias: dict[int, tuple[int, Categoria]] = {}  # id → (usuario_id, categoría)
_siguiente_id = _PRIMER_ID_PROPIO


def reiniciar() -> None:
    """Borra las categorías propias. Solo para tests."""
    global _siguiente_id
    _propias.clear()
    _siguiente_id = _PRIMER_ID_PROPIO


def ref(categoria: Categoria) -> CategoriaRef:
    """La forma que llevan los movimientos."""
    return CategoriaRef(id=categoria.id, nombre=categoria.nombre, tipo=categoria.tipo)


def predeterminada(nombre: str) -> Categoria:
    return next(c for c in _PREDETERMINADAS if c.nombre == nombre)


def _de_usuario(usuario_id: int) -> list[Categoria]:
    return [c for dueno, c in _propias.values() if dueno == usuario_id]


def listar(usuario_id: int) -> list[Categoria]:
    """Primero las predeterminadas y luego las propias, en el orden en que se crearon."""
    # TODO(backend): SELECT ... WHERE usuario_id IS NULL OR usuario_id = :usuario_id.
    return [*_PREDETERMINADAS, *_de_usuario(usuario_id)]


def obtener(usuario_id: int, id: int) -> Categoria | None:
    return next((c for c in listar(usuario_id) if c.id == id), None)


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
    # TODO(backend): INSERT con usuario_id.
    global _siguiente_id
    nombre = _validar(usuario_id, entrada, None)
    categoria = Categoria(id=_siguiente_id, nombre=nombre, tipo=entrada.tipo, predeterminada=False)
    _siguiente_id += 1
    _propias[categoria.id] = (usuario_id, categoria)
    return categoria


def actualizar(usuario_id: int, id: int, entrada: CategoriaEntrada) -> Categoria:
    # TODO(backend): UPDATE por id y usuario_id (nunca una predeterminada).
    from app.services import movimientos
    actual = _propia(usuario_id, id)
    nombre = _validar(usuario_id, entrada, actual)
    categoria = actual.model_copy(update={"nombre": nombre, "tipo": entrada.tipo})
    _propias[id] = (usuario_id, categoria)
    movimientos.cambiar_categoria(usuario_id, id, ref(categoria))  # los movimientos llevan el nombre
    return categoria


def eliminar(usuario_id: int, id: int, mover_a: int | None = None) -> None:
    """Si la categoría tiene movimientos, mover_a es la categoría (del mismo tipo) que los recibe."""
    # TODO(backend): UPDATE movimientos SET categoria_id = :mover_a y DELETE, en una transacción.
    from app.services import movimientos
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
        movimientos.cambiar_categoria(usuario_id, id, ref(destino))
    del _propias[id]


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
