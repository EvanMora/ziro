"""Movimientos: listar con filtros, crear, editar y eliminar.

Por ahora guarda todo en memoria del proceso (se pierde al reiniciar el servidor). Cada mes se
siembra con datos de prueba la primera vez que se pide, así cualquier mes tiene datos y los
tests con meses fijos dan siempre las mismas cifras. En el mes en curso solo se siembran los
días que ya pasaron.

TODO(backend): reemplazar el almacén por consultas filtradas por usuario_id. Las firmas, los
modelos de app/schemas/movimientos.py y las reglas de _validar() se mantienen.
"""
from datetime import date
from decimal import Decimal

from app.schemas.movimientos import (
    CategoriaRef,
    CuentaRef,
    FiltrosMovimientos,
    ListaMovimientos,
    Movimiento,
    MovimientoEntrada,
)
from app.services import categorias, cuentas
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

# Plantilla de cada mes: (día, descripción, categoría, cuenta, tipo, monto).
_PLANTILLA = [
    (31, "Salario", "Salario", "Cuenta de ahorros", "ingreso", "3200000"),
    (30, "Supermercado", "Mercado", "Billetera digital", "gasto", "184300"),
    (28, "Taxi", "Transporte", "Efectivo", "gasto", "62000"),
    (25, "Arriendo", "Arriendo", "Cuenta de ahorros", "gasto", "1100000"),
    (22, "Cine", "Ocio", "Billetera digital", "gasto", "48000"),
    (18, "Cena", "Ocio", "Cuenta de ahorros", "gasto", "132000"),
    (15, "Plaza de mercado", "Mercado", "Efectivo", "gasto", "200000"),
    (10, "Recarga tarjeta de transporte", "Transporte", "Billetera digital", "gasto", "148000"),
]

_movimientos: dict[int, Movimiento] = {}
_meses_sembrados: set[tuple[int, int]] = set()
_siguiente_id = 1


def hoy() -> date:
    return date.today()


def reiniciar() -> None:
    """Vacía el almacén. Solo para tests."""
    global _siguiente_id
    _movimientos.clear()
    _meses_sembrados.clear()
    _siguiente_id = 1


def _nuevo_id() -> int:
    global _siguiente_id
    _siguiente_id += 1
    return _siguiente_id - 1


def _ultimo_dia(anio: int, mes: int) -> int:
    siguiente = date(anio + mes // 12, mes % 12 + 1, 1)
    return (siguiente - date(anio, mes, 1)).days


def _sembrar(anio: int, mes: int) -> None:
    if (anio, mes) in _meses_sembrados:
        return
    _meses_sembrados.add((anio, mes))
    ultimo = _ultimo_dia(anio, mes)
    limite = hoy()
    # De la más vieja a la más nueva, para que los ids crezcan con la fecha.
    for dia, descripcion, categoria, cuenta, tipo, monto in reversed(_PLANTILLA):
        fecha = date(anio, mes, min(dia, ultimo))
        ref_cuenta = cuentas.ref_plantilla(cuenta)  # None si la persona eliminó esa cuenta
        if fecha > limite or ref_cuenta is None:
            continue
        nuevo = Movimiento(id=_nuevo_id(), fecha=fecha, descripcion=descripcion,
                           categoria=categorias.ref(categorias.predeterminada(categoria)),
                           cuenta=ref_cuenta, tipo=tipo, monto=Decimal(monto))
        _movimientos[nuevo.id] = nuevo


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
    """Los movimientos con fecha >= fecha. Antes siembra cada mes desde ahí hasta hoy, para que
    los saldos no dependan de qué meses se hayan visitado."""
    # TODO(backend): SELECT ... WHERE usuario_id = :usuario_id AND fecha >= :fecha.
    anio, mes = fecha.year, fecha.month
    limite = hoy()
    while (anio, mes) <= (limite.year, limite.month):
        _sembrar(anio, mes)
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return [m for m in _movimientos.values() if m.fecha >= fecha]


def usos_por_cuenta(usuario_id: int) -> dict[int, int]:
    """Cuántos movimientos tiene cada cuenta, en los meses ya sembrados."""
    # TODO(backend): SELECT cuenta_id, COUNT(*) ... GROUP BY cuenta_id.
    usos: dict[int, int] = {}
    for m in _movimientos.values():
        usos[m.cuenta.id] = usos.get(m.cuenta.id, 0) + 1
    return usos


def cambiar_cuenta(usuario_id: int, de_id: int, a: CuentaRef) -> None:
    """Pone la cuenta "a" en los movimientos de la cuenta de_id: renombrar (de_id == a.id) o
    pasar los movimientos de una cuenta que se va a eliminar."""
    for id, m in _movimientos.items():
        if m.cuenta.id == de_id:
            _movimientos[id] = m.model_copy(update={"cuenta": a})


def usos_por_categoria(usuario_id: int) -> dict[int, int]:
    """Cuántos movimientos tiene cada categoría, contando todos los meses."""
    # TODO(backend): SELECT categoria_id, COUNT(*) ... GROUP BY categoria_id.
    usos: dict[int, int] = {}
    for m in _movimientos.values():
        usos[m.categoria.id] = usos.get(m.categoria.id, 0) + 1
    return usos


def cambiar_categoria(usuario_id: int, de_id: int, a: CategoriaRef) -> None:
    """Pone la categoría "a" en los movimientos de la categoría de_id. Sirve para renombrar
    (de_id == a.id) y para pasar los movimientos de una categoría que se va a eliminar."""
    # TODO(backend): con la tabla de movimientos no hace falta al renombrar; al eliminar es un UPDATE.
    for id, m in _movimientos.items():
        if m.categoria.id == de_id:
            _movimientos[id] = m.model_copy(update={"categoria": a})


def listar(usuario_id: int, anio: int, mes: int, filtros: FiltrosMovimientos | None = None) -> ListaMovimientos:
    # TODO(backend): SELECT de los movimientos de usuario_id en el mes, con los filtros.
    filtros = filtros or FiltrosMovimientos()
    _sembrar(anio, mes)
    buscar = _normalizar((filtros.q or "").strip())
    encontrados = sorted(
        (m for m in _movimientos.values()
         if m.fecha.year == anio and m.fecha.month == mes and _coincide(m, filtros, buscar)),
        key=lambda m: (m.fecha, m.id),
        reverse=True,
    )
    return ListaMovimientos(
        anio=anio,
        mes=mes,
        filtros=filtros,
        movimientos=encontrados,
        ingresos=sum((m.monto for m in encontrados if m.tipo == "ingreso"), Decimal(0)),
        gastos=sum((m.monto for m in encontrados if m.tipo == "gasto"), Decimal(0)),
    )


def obtener(usuario_id: int, id: int) -> Movimiento | None:
    # TODO(backend): SELECT por id y usuario_id.
    return _movimientos.get(id)


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
    # Sembrar el mes de destino antes de guardar, para que una siembra posterior no lo pise.
    _sembrar(entrada.fecha.year, entrada.fecha.month)
    movimiento = Movimiento(id=id, fecha=entrada.fecha, descripcion=descripcion, categoria=categoria,
                            cuenta=cuenta, tipo=entrada.tipo, monto=_normalizar_monto(entrada.monto))
    _movimientos[id] = movimiento
    return movimiento


def crear(usuario_id: int, entrada: MovimientoEntrada) -> Movimiento:
    # TODO(backend): INSERT con usuario_id.
    _validar(usuario_id, entrada)
    _sembrar(entrada.fecha.year, entrada.fecha.month)  # antes del id, para que el nuevo sea el mayor
    return _guardar(usuario_id, _nuevo_id(), entrada)


def actualizar(usuario_id: int, id: int, entrada: MovimientoEntrada) -> Movimiento:
    # TODO(backend): UPDATE por id y usuario_id.
    if id not in _movimientos:
        raise NoEncontrado(id)
    return _guardar(usuario_id, id, entrada)


def eliminar(usuario_id: int, id: int) -> None:
    # TODO(backend): DELETE por id y usuario_id.
    if _movimientos.pop(id, None) is None:
        raise NoEncontrado(id)
