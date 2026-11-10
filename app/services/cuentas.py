"""Cuentas: dinero (ahorros, corriente, billetera, efectivo) y tarjetas de crédito.

Saldos (ver docs/superpowers/specs/2026-11-02-cuentas-design.md):
- Dinero: inicial + ingresos − gastos, contando solo movimientos con fecha >= creada_en.
- Tarjeta: la deuda es inicial + gastos − ingresos (un ingreso a una tarjeta es una devolución).
  Disponible = cupo − deuda.
- Editar el "saldo de hoy" ajusta inicial en la diferencia: no es un movimiento.
- Pagos de tarjeta: bajan la deuda de la tarjeta y el saldo de la cuenta de origen (cada uno desde
  su creada_en). No son movimientos: no suman en ingresos ni gastos en ningún lado.

Reglas: nombre obligatorio, de hasta MAX_NOMBRE caracteres y único entre las cuentas de la persona
(sin tildes ni mayúsculas); una cuenta con movimientos no pasa de dinero a tarjeta ni al revés;
eliminarla con movimientos exige pasarlos a otra cuenta del mismo grupo, y si no hay otra, no se
elimina. Nunca se borran movimientos.

El usuario demo empieza con las tres cuentas que usa la plantilla de services/movimientos.py y una
tarjeta. Se crean el primer día del mes anterior a hoy(), así solo cuentan uno o dos meses de la
plantilla y ninguna queda en negativo.

Por ahora todo vive en memoria del proceso. TODO(backend): tabla Cuenta con usuario_id; los saldos
salen de SUMs sobre movimientos con fecha >= creada_en. Las firmas y los modelos se mantienen.

services/movimientos.py importa este módulo. Las funciones de aquí que necesitan los movimientos
lo importan adentro para no formar un ciclo (igual que services/categorias.py).
"""
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.schemas.cuentas import (
    Cuenta,
    CuentaConSaldo,
    CuentaEntrada,
    Pago,
    PagoEntrada,
    PanelCuentas,
)
from app.schemas.movimientos import CuentaRef, FiltrosMovimientos, Movimiento
from app.services.comun import ErrorValidacion, NoEncontrado, limpiar_texto, normalizar
from app.web.formato import dinero

MAX_NOMBRE = 40
MAX_CUENTAS = 30  # por usuario

# TODO(backend): quitar cuando exista el registro de usuarios; hoy solo el demo tiene cuentas de prueba.
DEMO_USUARIO_ID = 1
# (id, nombre, tipo, icono, tono, inicial, cupo, dia_pago)
_DEMO = [
    (1, "Cuenta de ahorros", "ahorros", "banco", "azul", "1644400", None, None),
    (2, "Billetera digital", "billetera", "celular", "ciruela", "1053300", None, None),
    (3, "Efectivo", "efectivo", "billetes", "cafe", "707500", None, None),
    (4, "Tarjeta de crédito", "tarjeta", "tarjeta", "violeta", "840000", "3000000", 15),
]
# Nombres que usa la plantilla de movimientos → id de la cuenta demo.
_PLANTILLA = {"Cuenta de ahorros": 1, "Billetera digital": 2, "Efectivo": 3}
_PRIMER_ID = 100



@dataclass
class _PagoGuardado:
    usuario_id: int
    tarjeta_id: int
    origen_id: int
    monto: Decimal
    fecha: date


_cuentas: dict[int, tuple[int, Cuenta]] = {}  # id → (usuario_id, cuenta)
_pagos: dict[int, _PagoGuardado] = {}
_demo_creado = False
_siguiente_id = _PRIMER_ID
_siguiente_pago = 1


def reiniciar() -> None:
    """Vuelve al estado inicial (el demo se crea de nuevo al pedirlo). Solo para tests."""
    global _demo_creado, _siguiente_id, _siguiente_pago
    _cuentas.clear()
    _pagos.clear()
    _demo_creado = False
    _siguiente_id = _PRIMER_ID
    _siguiente_pago = 1


def es_tarjeta(tipo: str) -> bool:
    return tipo == "tarjeta"


def ref(c: Cuenta) -> CuentaRef:
    """La forma que llevan los movimientos."""
    return CuentaRef(id=c.id, nombre=c.nombre)


def _hoy() -> date:
    from app.services import movimientos
    return movimientos.hoy()


def _mes_anterior(d: date) -> date:
    return date(d.year - 1, 12, 1) if d.month == 1 else date(d.year, d.month - 1, 1)


def _crear_demo() -> None:
    global _demo_creado
    if _demo_creado:
        return
    _demo_creado = True
    creada_en = _mes_anterior(_hoy())
    for id, nombre, tipo, icono, tono, inicial, cupo, dia_pago in _DEMO:
        _cuentas[id] = (DEMO_USUARIO_ID, Cuenta(
            id=id, nombre=nombre, tipo=tipo, icono=icono, tono=tono, creada_en=creada_en,
            inicial=Decimal(inicial), cupo=Decimal(cupo) if cupo else None, dia_pago=dia_pago))


def listar(usuario_id: int) -> list[Cuenta]:
    """En el orden en que se crearon."""
    # TODO(backend): SELECT ... WHERE usuario_id = :usuario_id ORDER BY id.
    if usuario_id == DEMO_USUARIO_ID:
        _crear_demo()
    return [c for dueno, c in _cuentas.values() if dueno == usuario_id]


def obtener(usuario_id: int, id: int) -> Cuenta | None:
    return next((c for c in listar(usuario_id) if c.id == id), None)


def ref_plantilla(nombre: str) -> CuentaRef | None:
    """La cuenta demo que usa una fila de la plantilla de movimientos, con su nombre actual.
    None si la persona la eliminó: esa fila no se siembra."""
    cuenta = obtener(DEMO_USUARIO_ID, _PLANTILLA[nombre])
    return ref(cuenta) if cuenta else None


def proxima_fecha_pago(dia_pago: int, hoy: date) -> date:
    """La próxima vez que llega dia_pago (hoy cuenta). En meses más cortos, su último día."""
    def en_mes(anio: int, mes: int) -> date:
        return date(anio, mes, min(dia_pago, monthrange(anio, mes)[1]))

    fecha = en_mes(hoy.year, hoy.month)
    if fecha >= hoy:
        return fecha
    return en_mes(hoy.year + 1, 1) if hoy.month == 12 else en_mes(hoy.year, hoy.month + 1)


# ---------- Saldos ----------

def _efecto(c: Cuenta, m: Movimiento) -> Decimal:
    """Cuánto cambia un movimiento el saldo (dinero) o la deuda (tarjeta) de la cuenta c."""
    suma = m.monto if m.tipo == "ingreso" else -m.monto
    return -suma if es_tarjeta(c.tipo) else suma


def _pagos_de(usuario_id: int) -> list[tuple[int, _PagoGuardado]]:
    return [(id, p) for id, p in _pagos.items() if p.usuario_id == usuario_id]


def _saldos(usuario_id: int, lista: list[Cuenta], sin_pago: int | None = None) -> dict[int, Decimal]:
    """Saldo (dinero) o deuda (tarjeta) de hoy de cada cuenta. sin_pago deja fuera un pago: el que
    se está editando, para no contar su monto anterior."""
    from app.services import movimientos
    if not lista:
        return {}
    movs = movimientos.desde(usuario_id, min(c.creada_en for c in lista))
    saldos = {c.id: c.inicial for c in lista}
    por_id = {c.id: c for c in lista}
    for m in movs:
        c = por_id.get(m.cuenta.id)
        if c and m.fecha >= c.creada_en:
            saldos[c.id] += _efecto(c, m)
    for id, p in _pagos_de(usuario_id):
        if id == sin_pago:
            continue
        for cuenta_id in (p.tarjeta_id, p.origen_id):  # baja la deuda de una y el saldo de la otra
            c = por_id.get(cuenta_id)
            if c and p.fecha >= c.creada_en:
                saldos[c.id] -= p.monto
    return saldos


def _pagos_por_cuenta(usuario_id: int) -> dict[int, int]:
    """Cuántos pagos tiene cada cuenta, como tarjeta o como cuenta de origen."""
    cuantos: dict[int, int] = {}
    for _, p in _pagos_de(usuario_id):
        for cuenta_id in (p.tarjeta_id, p.origen_id):
            cuantos[cuenta_id] = cuantos.get(cuenta_id, 0) + 1
    return cuantos


def _usos_por_cuenta(usuario_id: int) -> dict[int, int]:
    """Movimientos (de los meses ya sembrados) y pagos de cada cuenta."""
    from app.services import movimientos
    usos = movimientos.usos_por_cuenta(usuario_id)
    for cuenta_id, cuantos in _pagos_por_cuenta(usuario_id).items():
        usos[cuenta_id] = usos.get(cuenta_id, 0) + cuantos
    return usos


def _usos(usuario_id: int, c: Cuenta) -> int:
    from app.services import movimientos
    movimientos.desde(usuario_id, c.creada_en)  # siembra los meses que importan antes de contar
    return _usos_por_cuenta(usuario_id).get(c.id, 0)


def saldos(usuario_id: int, lista: list[Cuenta] | None = None) -> dict[int, Decimal]:
    """Saldo (dinero) o deuda (tarjeta) de hoy de cada cuenta, por id: lo que usa el Resumen. Es la
    parte barata de panel(), sin contar los movimientos y pagos de cada cuenta (eso recorre todos
    los movimientos). lista: las cuentas, si la ruta ya las leyó con listar()."""
    return _saldos(usuario_id, listar(usuario_id) if lista is None else lista)


def panel(usuario_id: int) -> PanelCuentas:
    lista = listar(usuario_id)
    saldos = _saldos(usuario_id, lista)
    usos = _usos_por_cuenta(usuario_id)  # _saldos ya sembró desde la cuenta más vieja
    pagos = _pagos_por_cuenta(usuario_id)
    hoy = _hoy()
    dinero, tarjetas = [], []
    for c in lista:
        saldo = saldos[c.id]
        if es_tarjeta(c.tipo):
            fecha = proxima_fecha_pago(c.dia_pago, hoy)
            tarjetas.append(CuentaConSaldo(cuenta=c, saldo=saldo, disponible=c.cupo - saldo, fecha_limite=fecha,
                                           dias_para_pagar=(fecha - hoy).days, usos=usos.get(c.id, 0),
                                           pagos=pagos.get(c.id, 0)))
        else:
            dinero.append(CuentaConSaldo(cuenta=c, saldo=saldo, disponible=None, fecha_limite=None,
                                         dias_para_pagar=None, usos=usos.get(c.id, 0), pagos=pagos.get(c.id, 0)))
    tarjetas.sort(key=lambda t: (t.fecha_limite, t.cuenta.nombre))
    tienes = sum((c.saldo for c in dinero), Decimal(0))
    debes = sum((t.saldo for t in tarjetas), Decimal(0))
    return PanelCuentas(dinero=dinero, tarjetas=tarjetas, tienes=tienes, debes=debes, te_queda=tienes - debes)


# ---------- Crear, editar y eliminar ----------

def _validar(usuario_id: int, e: CuentaEntrada, actual: Cuenta | None) -> str:
    """Devuelve el nombre limpio o lanza ErrorValidacion."""
    from app.services.movimientos import MAX_MONTO, _normalizar_monto
    errores: dict[str, str] = {}
    tarjeta = es_tarjeta(e.tipo)

    nombre = limpiar_texto(e.nombre)
    if not nombre:
        errores["nombre"] = "Escribe un nombre."
    elif len(nombre) > MAX_NOMBRE:
        errores["nombre"] = f"Máximo {MAX_NOMBRE} caracteres."
    elif any(normalizar(c.nombre) == normalizar(nombre)
             for c in listar(usuario_id) if actual is None or c.id != actual.id):
        errores["nombre"] = "Ya tienes una cuenta con ese nombre."

    cambia_grupo = actual is not None and es_tarjeta(actual.tipo) != tarjeta
    sin_saldo = e.saldo is None and (actual is None or cambia_grupo)
    if sin_saldo or (e.saldo is not None and (not e.saldo.is_finite() or e.saldo < 0)):
        errores["saldo"] = "Escribe una deuda de 0 o más." if tarjeta else "Escribe un saldo de 0 o más."
    elif e.saldo is not None and e.saldo >= MAX_MONTO:
        errores["saldo"] = "El monto es demasiado grande."

    if tarjeta:
        if e.cupo is None or not e.cupo.is_finite() or _normalizar_monto(e.cupo) <= 0:
            errores["cupo"] = "Escribe un cupo mayor que 0."
        elif e.cupo >= MAX_MONTO:
            errores["cupo"] = "El monto es demasiado grande."
        if e.dia_pago is None or not 1 <= e.dia_pago <= 31:
            errores["dia_pago"] = "Elige un día entre 1 y 31."

    if actual is None and len(listar(usuario_id)) >= MAX_CUENTAS:
        errores["general"] = f"Llegaste al máximo de {MAX_CUENTAS} cuentas."
    if actual is not None and es_tarjeta(actual.tipo) != tarjeta and _usos(usuario_id, actual):
        errores["tipo"] = "Ya tiene movimientos: no puede pasar de dinero a tarjeta ni al revés."
    if errores:
        raise ErrorValidacion(errores)
    return nombre


def _normalizada(e: CuentaEntrada) -> CuentaEntrada:
    """Saldo y cupo sin exponente ("1E+3" → 1000) y con a lo sumo 2 decimales, como los pagos."""
    from app.services.movimientos import _normalizar_monto
    return e.model_copy(update={"saldo": _normalizar_monto(e.saldo) if e.saldo is not None else None,
                                "cupo": _normalizar_monto(e.cupo) if e.cupo is not None else None})


def _datos(e: CuentaEntrada, nombre: str) -> dict:
    tarjeta = es_tarjeta(e.tipo)
    return {"nombre": nombre, "tipo": e.tipo, "icono": e.icono, "tono": e.tono,
            "cupo": e.cupo if tarjeta else None, "dia_pago": e.dia_pago if tarjeta else None}


def _texto_usos(movimientos: int, pagos: int) -> str:
    """"Tiene 1 movimiento y 2 pagos. Elige a qué cuenta pasarlos." (o "pasarlo" si es uno solo)."""
    partes = []
    if movimientos:
        partes.append("1 movimiento" if movimientos == 1 else f"{movimientos} movimientos")
    if pagos:
        partes.append("1 pago" if pagos == 1 else f"{pagos} pagos")
    pronombre = "pasarlo" if movimientos + pagos == 1 else "pasarlos"
    return f"Tiene {' y '.join(partes)}. Elige a qué cuenta {pronombre}."


def crear(usuario_id: int, e: CuentaEntrada) -> Cuenta:
    # TODO(backend): INSERT con usuario_id.
    global _siguiente_id
    nombre = _validar(usuario_id, e, None)
    e = _normalizada(e)
    cuenta = Cuenta(id=_siguiente_id, creada_en=_hoy(), inicial=e.saldo, **_datos(e, nombre))
    _siguiente_id += 1
    _cuentas[cuenta.id] = (usuario_id, cuenta)
    return cuenta


def actualizar(usuario_id: int, id: int, e: CuentaEntrada) -> Cuenta:
    # TODO(backend): UPDATE por id y usuario_id.
    from app.services import movimientos
    actual = obtener(usuario_id, id)
    if actual is None:
        raise NoEncontrado(id)
    nombre = _validar(usuario_id, e, actual)
    e = _normalizada(e)
    if es_tarjeta(actual.tipo) != es_tarjeta(e.tipo):
        inicial = e.saldo  # sin movimientos (lo validó _validar): el saldo de hoy es el punto de partida
    elif e.saldo is None:
        inicial = actual.inicial  # no se tocó el saldo
    else:
        inicial = actual.inicial + e.saldo - _saldos(usuario_id, [actual])[id]
    cuenta = actual.model_copy(update=_datos(e, nombre) | {"inicial": inicial})
    _cuentas[id] = (usuario_id, cuenta)
    movimientos.cambiar_cuenta(usuario_id, id, ref(cuenta))  # los movimientos llevan el nombre
    return cuenta


def eliminar(usuario_id: int, id: int, mover_a: int | None = None) -> None:
    """Si la cuenta tiene movimientos, mover_a es la cuenta (del mismo grupo) que los recibe."""
    # TODO(backend): UPDATE de movimientos y DELETE, en una transacción.
    from app.services import movimientos
    cuenta = obtener(usuario_id, id)
    if cuenta is None:
        raise NoEncontrado(id)
    usos = _usos(usuario_id, cuenta)
    if usos:
        tarjeta = es_tarjeta(cuenta.tipo)
        otras = [c for c in listar(usuario_id) if c.id != id and es_tarjeta(c.tipo) == tarjeta]
        destino = obtener(usuario_id, mover_a) if mover_a is not None else None
        if not otras:
            unica = "tu única tarjeta" if tarjeta else "tu única cuenta de dinero"
            raise ErrorValidacion({"mover_a": f"Es {unica}. Crea otra para pasarle sus movimientos antes de eliminarla."})
        if mover_a is None:
            pagos = _pagos_por_cuenta(usuario_id).get(id, 0)
            raise ErrorValidacion({"mover_a": _texto_usos(usos - pagos, pagos)})
        if destino is None or destino.id == id:
            raise ErrorValidacion({"mover_a": "Elige otra cuenta."})
        if es_tarjeta(destino.tipo) != tarjeta:
            raise ErrorValidacion({"mover_a": "Elige una tarjeta." if tarjeta else "Elige una cuenta de dinero."})
        movimientos.cambiar_cuenta(usuario_id, id, ref(destino))
        for _, p in _pagos_de(usuario_id):
            if p.tarjeta_id == id:
                p.tarjeta_id = destino.id
            if p.origen_id == id:
                p.origen_id = destino.id
    del _cuentas[id]


# ---------- Pagos de tarjeta ----------

def _leer_pago(id: int, p: _PagoGuardado) -> Pago:
    tarjeta = obtener(p.usuario_id, p.tarjeta_id)
    origen = obtener(p.usuario_id, p.origen_id)
    return Pago(id=id, fecha=p.fecha, monto=p.monto, tarjeta=ref(tarjeta), origen=ref(origen),
                tarjeta_icono=tarjeta.icono, tarjeta_tono=tarjeta.tono)


def obtener_pago(usuario_id: int, id: int) -> Pago | None:
    p = _pagos.get(id)
    return _leer_pago(id, p) if p and p.usuario_id == usuario_id else None


def _validar_pago(usuario_id: int, tarjeta: Cuenta, e: PagoEntrada, pago_id: int | None) -> tuple[Cuenta, Decimal]:
    """Devuelve la cuenta de origen y el monto normalizado, o lanza ErrorValidacion.

    Un pago con fecha anterior a la creación de una cuenta no la afecta (regla de creada_en), así
    que la deuda o el saldo solo se revisan en las cuentas que el pago sí mueve. Al editar, la
    fecha se compara con la creación solo si cambió: un pago que pasó a una tarjeta más nueva
    (al eliminar la suya) se puede seguir editando."""
    from app.services import movimientos
    errores: dict[str, str] = {}
    monto = None
    if not e.monto.is_finite() or e.monto <= 0:
        errores["monto"] = "Escribe un monto mayor que 0."
    elif e.monto >= movimientos.MAX_MONTO:
        errores["monto"] = "El monto es demasiado grande."
    else:
        monto = movimientos._normalizar_monto(e.monto)
        if monto <= 0:  # "0.001" pasa "> 0" pero se guardaría como 0,00
            errores["monto"] = "Escribe un monto mayor que 0."
            monto = None

    origen = obtener(usuario_id, e.cuenta_origen_id)
    if origen is None or es_tarjeta(origen.tipo):
        errores["cuenta_origen_id"] = "Elige de qué cuenta sale el pago."
        origen = None

    anterior = _pagos.get(pago_id) if pago_id is not None else None
    fecha_nueva = anterior is None or e.fecha != anterior.fecha
    if e.fecha > _hoy():
        errores["fecha"] = "La fecha no puede ser futura."
    elif fecha_nueva and (e.fecha < tarjeta.creada_en or (origen and e.fecha < origen.creada_en)):
        errores["fecha"] = "La fecha es anterior a la creación de la cuenta."

    if monto is not None:
        saldos = _saldos(usuario_id, [tarjeta, *([origen] if origen else [])], sin_pago=pago_id)
        if e.fecha >= tarjeta.creada_en and monto > saldos[tarjeta.id]:
            errores["monto"] = f"No puedes pagar más de lo que debes ({dinero(saldos[tarjeta.id])})."
        elif origen and e.fecha >= origen.creada_en and monto > saldos[origen.id]:
            errores["cuenta_origen_id"] = f"No te alcanza: {origen.nombre} tiene {dinero(saldos[origen.id])}."
    if errores:
        raise ErrorValidacion(errores)
    return origen, monto


def _tarjeta(usuario_id: int, id: int) -> Cuenta:
    tarjeta = obtener(usuario_id, id)
    if tarjeta is None:
        raise NoEncontrado(id)
    if not es_tarjeta(tarjeta.tipo):
        raise ErrorValidacion({"general": "Solo se le pueden registrar pagos a una tarjeta."})
    return tarjeta


def registrar_pago(usuario_id: int, tarjeta_id: int, e: PagoEntrada) -> Pago:
    # TODO(backend): INSERT en PagoTarjeta con usuario_id.
    global _siguiente_pago
    tarjeta = _tarjeta(usuario_id, tarjeta_id)
    origen, monto = _validar_pago(usuario_id, tarjeta, e, None)
    id = _siguiente_pago
    _siguiente_pago += 1
    _pagos[id] = _PagoGuardado(usuario_id, tarjeta.id, origen.id, monto, e.fecha)
    return _leer_pago(id, _pagos[id])


def actualizar_pago(usuario_id: int, id: int, e: PagoEntrada) -> Pago:
    """Cambia monto, cuenta de origen o fecha. La tarjeta no cambia."""
    # TODO(backend): UPDATE por id y usuario_id.
    p = _pagos.get(id)
    if p is None or p.usuario_id != usuario_id:
        raise NoEncontrado(id)
    tarjeta = _tarjeta(usuario_id, p.tarjeta_id)
    origen, monto = _validar_pago(usuario_id, tarjeta, e, id)
    _pagos[id] = _PagoGuardado(usuario_id, tarjeta.id, origen.id, monto, e.fecha)
    return _leer_pago(id, _pagos[id])


def eliminar_pago(usuario_id: int, id: int) -> None:
    # TODO(backend): DELETE por id y usuario_id.
    p = _pagos.get(id)
    if p is None or p.usuario_id != usuario_id:
        raise NoEncontrado(id)
    del _pagos[id]


def pagos_del_mes(usuario_id: int, anio: int, mes: int, filtros: FiltrosMovimientos) -> list[Pago]:
    """Los pagos del mes que deja ver el filtro de Movimientos, del más nuevo al más viejo. No son
    gastos ni ingresos ni tienen categoría: con esos filtros no aparece ninguno."""
    # TODO(backend): SELECT de PagoTarjeta del mes con los filtros.
    if filtros.tipo or filtros.categoria_id:
        return []
    buscar = normalizar((filtros.q or "").strip())
    pagos = []
    for id, p in _pagos_de(usuario_id):
        if (p.fecha.year, p.fecha.month) != (anio, mes):
            continue
        if filtros.cuenta_id and filtros.cuenta_id not in (p.tarjeta_id, p.origen_id):
            continue
        pago = _leer_pago(id, p)
        if buscar and buscar not in normalizar(f"Pago {pago.tarjeta.nombre} {pago.origen.nombre}"):
            continue
        pagos.append(pago)
    return sorted(pagos, key=lambda x: (x.fecha, x.id), reverse=True)
