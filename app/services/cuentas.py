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

Las cuentas y los pagos viven en las tablas `cuentas` y `pagos_tarjeta` (app/models/cuentas.py y
app/models/pagos_tarjeta.py). Las firmas y los modelos se mantienen.
Una persona nueva empieza sin cuentas.
"""
from calendar import monthrange
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select, update

from app.models.cuentas import CuentaDB
from app.models.movimientos import MovimientoDB
from app.models.pagos_tarjeta import PagoTarjetaDB
from app.schemas.cuentas import (
    Cuenta,
    CuentaConSaldo,
    CuentaEntrada,
    Pago,
    PagoEntrada,
    PanelCuentas,
)
from app.schemas.movimientos import CuentaRef, FiltrosMovimientos, Movimiento
from app.services import database
from app.services.comun import (
    ErrorValidacion,
    NoEncontrado,
    limpiar_texto,
    normalizar,
)
from app.web.formato import dinero

MAX_NOMBRE = 40
MAX_CUENTAS = 30  # por usuario

def reiniciar() -> None:
    """Vacía la base. Solo para tests."""
    database.reiniciar()


def es_tarjeta(tipo: str) -> bool:
    return tipo == "tarjeta"


def ref(c: Cuenta) -> CuentaRef:
    """La forma que llevan los movimientos."""
    return CuentaRef(id=c.id, nombre=c.nombre)


def _hoy() -> date:
    from app.services import movimientos
    return movimientos.hoy()


def _como_cuenta(fila: CuentaDB) -> Cuenta:
    from app.services.movimientos import _normalizar_monto
    return Cuenta(
        id=fila.id, nombre=fila.nombre, tipo=fila.tipo, icono=fila.icono, tono=fila.tono,
        creada_en=fila.creada_en, inicial=_normalizar_monto(fila.inicial),
        cupo=_normalizar_monto(fila.cupo) if fila.cupo is not None else None,
        dia_pago=fila.dia_pago,
    )


def listar(usuario_id: int) -> list[Cuenta]:
    """En el orden en que se crearon."""
    with database.sesion() as db:
        filas = db.execute(
            select(CuentaDB).where(CuentaDB.usuario_id == usuario_id).order_by(CuentaDB.id)
        ).scalars().all()
        return [_como_cuenta(f) for f in filas]


def obtener(usuario_id: int, id: int) -> Cuenta | None:
    return next((c for c in listar(usuario_id) if c.id == id), None)


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


def _pagos_de(usuario_id: int) -> list[tuple[int, int, int, Decimal, date]]:
    """Los pagos del usuario como tuplas (id, tarjeta_id, origen_id, monto, fecha), para no
    arrastrar objetos de la sesión fuera de ella."""
    from app.services import movimientos
    with database.sesion() as db:
        return [
            (p.id, p.tarjeta_id, p.origen_id, movimientos._normalizar_monto(p.monto), p.fecha)
            for p in db.execute(
                select(PagoTarjetaDB)
                .where(PagoTarjetaDB.usuario_id == usuario_id)
                .order_by(PagoTarjetaDB.id)
            ).scalars().all()
        ]


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
    for id_pago, tarjeta_id, origen_id, monto, fecha in _pagos_de(usuario_id):
        if id_pago == sin_pago:
            continue
        for cuenta_id in (tarjeta_id, origen_id):  # baja la deuda de una y el saldo de la otra
            c = por_id.get(cuenta_id)
            if c and fecha >= c.creada_en:
                saldos[c.id] -= monto
    from app.services import movimientos
    return {id_: movimientos._normalizar_monto(v) for id_, v in saldos.items()}


def _pagos_por_cuenta(usuario_id: int) -> dict[int, int]:
    """Cuántos pagos tiene cada cuenta, como tarjeta o como cuenta de origen."""
    cuantos: dict[int, int] = {}
    with database.sesion() as db:
        for columna in (PagoTarjetaDB.tarjeta_id, PagoTarjetaDB.origen_id):
            for cuenta_id, n in db.execute(
                select(columna, func.count(PagoTarjetaDB.id))
                .where(PagoTarjetaDB.usuario_id == usuario_id)
                .group_by(columna)
            ).all():
                cuantos[cuenta_id] = cuantos.get(cuenta_id, 0) + n
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
    from app.services import movimientos
    _nm = movimientos._normalizar_monto
    dinero, tarjetas = [], []
    for c in lista:
        saldo = saldos[c.id]
        if es_tarjeta(c.tipo):
            fecha = proxima_fecha_pago(c.dia_pago, hoy)
            tarjetas.append(CuentaConSaldo(cuenta=c, saldo=saldo, disponible=_nm(c.cupo - saldo), fecha_limite=fecha,
                                           dias_para_pagar=(fecha - hoy).days, usos=usos.get(c.id, 0),
                                           pagos=pagos.get(c.id, 0)))
        else:
            dinero.append(CuentaConSaldo(cuenta=c, saldo=saldo, disponible=None, fecha_limite=None,
                                         dias_para_pagar=None, usos=usos.get(c.id, 0),
                                         pagos=pagos.get(c.id, 0)))
    tarjetas.sort(key=lambda t: (t.fecha_limite, t.cuenta.nombre))
    tienes = _nm(sum((c.saldo for c in dinero), Decimal(0)))
    debes = _nm(sum((t.saldo for t in tarjetas), Decimal(0)))
    return PanelCuentas(dinero=dinero, tarjetas=tarjetas, tienes=tienes, debes=debes, te_queda=_nm(tienes - debes))


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


def _datos(e: CuentaEntrada) -> dict:
    tarjeta = es_tarjeta(e.tipo)
    return {"nombre": e.nombre, "tipo": e.tipo, "icono": e.icono, "tono": e.tono,
            "cupo": e.cupo if tarjeta else None, "dia_pago": e.dia_pago if tarjeta else None}


def _texto_usos(movimientos: int, pagos: int) -> str:
    """"Tiene 1 movimiento y 2 pagos. Elige a qué cuenta pasarlos" (o "pasarlo" si es uno solo)."""
    partes = []
    if movimientos:
        partes.append("1 movimiento" if movimientos == 1 else f"{movimientos} movimientos")
    if pagos:
        partes.append("1 pago" if pagos == 1 else f"{pagos} pagos")
    pronombre = "pasarlo" if movimientos + pagos == 1 else "pasarlos"
    return f"Tiene {' y '.join(partes)}. Elige a qué cuenta {pronombre}."


def crear(usuario_id: int, e: CuentaEntrada) -> Cuenta:
    nombre = _validar(usuario_id, e, None)
    e = _normalizada(e)
    datos = _datos(e) | {"nombre": nombre}
    with database.sesion() as db:
        fila = CuentaDB(usuario_id=usuario_id, creada_en=_hoy(), inicial=e.saldo, **datos)
        db.add(fila)
        db.flush()
        id_cuenta = fila.id
    # Respuesta con los valores que se guardaron, sin re-leer de la BD: el contrato de la API
    # serializa el Decimal tal y como se normalizó (p. ej. 0.001 → "0.00").
    return Cuenta(id=id_cuenta, creada_en=_hoy(), inicial=e.saldo, **datos)


def actualizar(usuario_id: int, id: int, e: CuentaEntrada) -> Cuenta:
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
    datos = _datos(e) | {"nombre": nombre, "inicial": inicial}
    with database.sesion() as db:
        db.execute(
            update(CuentaDB).where(CuentaDB.id == id, CuentaDB.usuario_id == usuario_id).values(**datos)
        )
    return actual.model_copy(update=datos)


def eliminar(usuario_id: int, id: int, mover_a: int | None = None) -> None:
    """Si la cuenta tiene movimientos, mover_a es la cuenta (del mismo grupo) que los recibe."""
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
        # Reasignar y borrar en la misma transacción: no se pierde ningún movimiento ni pago.
        with database.sesion() as db:
            db.execute(
                update(MovimientoDB)
                .where(MovimientoDB.cuenta_id == id, MovimientoDB.usuario_id == usuario_id)
                .values(cuenta_id=destino.id)
            )
            db.execute(
                update(PagoTarjetaDB)
                .where(PagoTarjetaDB.tarjeta_id == id, PagoTarjetaDB.usuario_id == usuario_id)
                .values(tarjeta_id=destino.id)
            )
            db.execute(
                update(PagoTarjetaDB)
                .where(PagoTarjetaDB.origen_id == id, PagoTarjetaDB.usuario_id == usuario_id)
                .values(origen_id=destino.id)
            )
            db.execute(
                delete(CuentaDB).where(CuentaDB.id == id, CuentaDB.usuario_id == usuario_id)
            )
    else:
        with database.sesion() as db:
            borradas = db.execute(
                delete(CuentaDB).where(CuentaDB.id == id, CuentaDB.usuario_id == usuario_id)
            ).rowcount
            if not borradas:
                raise NoEncontrado(id)


# ---------- Pagos de tarjeta ----------

def _como_pago(fila: PagoTarjetaDB) -> Pago:
    tarjeta = obtener(fila.usuario_id, fila.tarjeta_id)
    origen = obtener(fila.usuario_id, fila.origen_id)
    from app.services import movimientos
    return Pago(id=fila.id, fecha=fila.fecha, monto=movimientos._normalizar_monto(fila.monto),
                tarjeta=ref(tarjeta), origen=ref(origen),
                tarjeta_icono=tarjeta.icono, tarjeta_tono=tarjeta.tono)


def obtener_pago(usuario_id: int, id: int) -> Pago | None:
    with database.sesion() as db:
        fila = db.execute(
            select(PagoTarjetaDB).where(PagoTarjetaDB.id == id, PagoTarjetaDB.usuario_id == usuario_id)
        ).scalar_one_or_none()
        return _como_pago(fila) if fila is not None else None


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

    anterior_fecha = None
    if pago_id is not None:
        with database.sesion() as db:
            fila = db.execute(
                select(PagoTarjetaDB).where(PagoTarjetaDB.id == pago_id,
                                            PagoTarjetaDB.usuario_id == usuario_id)
            ).scalar_one_or_none()
            if fila is not None:
                anterior_fecha = fila.fecha
    fecha_nueva = pago_id is None or e.fecha != anterior_fecha
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
    tarjeta = _tarjeta(usuario_id, tarjeta_id)
    origen, monto = _validar_pago(usuario_id, tarjeta, e, None)
    with database.sesion() as db:
        fila = PagoTarjetaDB(usuario_id=usuario_id, tarjeta_id=tarjeta.id, origen_id=origen.id,
                             monto=monto, fecha=e.fecha)
        db.add(fila)
        db.flush()
        id_pago = fila.id
    return obtener_pago(usuario_id, id_pago)


def actualizar_pago(usuario_id: int, id: int, e: PagoEntrada) -> Pago:
    """Cambia monto, cuenta de origen o fecha. La tarjeta no cambia."""
    anterior = obtener_pago(usuario_id, id)
    if anterior is None:
        raise NoEncontrado(id)
    tarjeta = _tarjeta(usuario_id, anterior.tarjeta.id)
    origen, monto = _validar_pago(usuario_id, tarjeta, e, id)
    with database.sesion() as db:
        db.execute(
            update(PagoTarjetaDB)
            .where(PagoTarjetaDB.id == id, PagoTarjetaDB.usuario_id == usuario_id)
            .values(origen_id=origen.id, monto=monto, fecha=e.fecha)
        )
    return obtener_pago(usuario_id, id)


def eliminar_pago(usuario_id: int, id: int) -> None:
    with database.sesion() as db:
        borradas = db.execute(
            delete(PagoTarjetaDB).where(PagoTarjetaDB.id == id, PagoTarjetaDB.usuario_id == usuario_id)
        ).rowcount
        if not borradas:
            raise NoEncontrado(id)


def pagos_del_mes(usuario_id: int, anio: int, mes: int, filtros: FiltrosMovimientos) -> list[Pago]:
    """Los pagos del mes que deja ver el filtro de Movimientos, del más nuevo al más viejo. No son
    gastos ni ingresos ni tienen categoría: con esos filtros no aparece ninguno."""
    if filtros.tipo or filtros.categoria_id:
        return []
    primero = date(anio, mes, 1)
    if mes == 12:
        siguiente = date(anio + 1, 1, 1)
    else:
        siguiente = date(anio, mes + 1, 1)
    buscar = normalizar((filtros.q or "").strip())
    with database.sesion() as db:
        filas = db.execute(
            select(PagoTarjetaDB)
            .where(PagoTarjetaDB.usuario_id == usuario_id,
                   PagoTarjetaDB.fecha >= primero, PagoTarjetaDB.fecha < siguiente)
            .order_by(PagoTarjetaDB.fecha.desc(), PagoTarjetaDB.id.desc())
        ).scalars().all()
        pagos = []
        for fila in filas:
            if filtros.cuenta_id and filtros.cuenta_id not in (fila.tarjeta_id, fila.origen_id):
                continue
            pago = _como_pago(fila)
            if buscar and buscar not in normalizar(f"Pago {pago.tarjeta.nombre} {pago.origen.nombre}"):
                continue
            pagos.append(pago)
        return pagos
