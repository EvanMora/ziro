"""Datos de prueba para los tests: el usuario 1 con sus cuentas, los movimientos de cada mes y el
presupuesto de ejemplo del mes anterior.

La app no siembra nada (spec 2026-11-16-crear-cuenta-design.md, sección 6). Para que los tests de
siempre sigan comprobando las mismas cifras, instalar() envuelve algunas funciones de los servicios y
siembra antes de llamarlas, igual que lo hacía la app: las cuentas al listarlas, cada mes la primera
vez que se pide (solo los días que ya pasaron en el mes en curso) y el presupuesto de ejemplo del mes
anterior a hoy(). Solo para el usuario USUARIO_PRUEBA_ID; los demás usuarios empiezan vacíos.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from argon2 import PasswordHasher
from sqlalchemy import func, select

from app.models.cuentas import CuentaDB
from app.models.movimientos import MovimientoDB
from app.models.presupuestos import PresupuestoDB
from app.models.usuarios import UsuarioDB
from app.schemas.auth import UsuarioSesion
from app.schemas.movimientos import CuentaRef
from app.services import categorias, cuentas, database, movimientos, presupuestos

USUARIO_PRUEBA_ID = 1
USUARIO_PRUEBA = UsuarioSesion(id=USUARIO_PRUEBA_ID, nombre="Evan Pro", correo="evanpro@correo.com",
                               iniciales="EP")
PASSWORD = "secreta123"
_HASH = PasswordHasher().hash(PASSWORD)  # una vez: Argon2 es lento a propósito

# (nombre, tipo, icono, tono, inicial, cupo, dia_pago). Se crean el primer día del mes anterior a
# hoy(), así solo cuentan uno o dos meses de la plantilla y ninguna queda en negativo.
_CUENTAS = [
    ("Cuenta de ahorros", "ahorros", "banco", "azul", "1644400", None, None),
    ("Billetera digital", "billetera", "celular", "ciruela", "1053300", None, None),
    ("Efectivo", "efectivo", "billetes", "cafe", "707500", None, None),
    ("Tarjeta de crédito", "tarjeta", "tarjeta", "violeta", "840000", "3000000", 15),
]
# Nombres que usa la plantilla de movimientos → id de la cuenta (la base se vacía en cada test).
_IDS_CUENTAS = {"Cuenta de ahorros": 1, "Billetera digital": 2, "Efectivo": 3}

# Plantilla de cada mes: (día, descripción, categoría, cuenta, tipo, monto).
_MOVIMIENTOS = [
    (31, "Salario", "Salario", "Cuenta de ahorros", "ingreso", "3200000"),
    (30, "Supermercado", "Mercado", "Billetera digital", "gasto", "184300"),
    (28, "Taxi", "Transporte", "Efectivo", "gasto", "62000"),
    (25, "Arriendo", "Arriendo", "Cuenta de ahorros", "gasto", "1100000"),
    (22, "Cine", "Ocio", "Billetera digital", "gasto", "48000"),
    (18, "Cena", "Ocio", "Cuenta de ahorros", "gasto", "132000"),
    (15, "Plaza de mercado", "Mercado", "Efectivo", "gasto", "200000"),
    (10, "Recarga tarjeta de transporte", "Transporte", "Billetera digital", "gasto", "148000"),
]

# El mes anterior al actual trae presupuesto, con una categoría en alerta y otra excedida frente a la
# plantilla de movimientos.
_PRESUPUESTO = {"Arriendo": "1100000", "Mercado": "450000", "Transporte": "300000", "Ocio": "150000"}


def crear_usuario(id: int = USUARIO_PRUEBA_ID, correo: str = USUARIO_PRUEBA.correo,
                  nombre: str = USUARIO_PRUEBA.nombre) -> None:
    """Inserta un usuario con id fijo (las cuentas, movimientos y presupuestos lo necesitan por la
    clave foránea)."""
    with database.sesion() as db:
        db.add(UsuarioDB(id=id, nombre=nombre, email=correo, password_hash=_HASH,
                         creado_en=datetime.now(timezone.utc)))
        db.flush()
        database.ajustar_secuencias(db)  # en Postgres, un id fijo no avanza la secuencia


def _mes_anterior(d: date) -> date:
    return date(d.year - 1, 12, 1) if d.month == 1 else date(d.year, d.month - 1, 1)


def _sembrar_cuentas(usuario_id: int) -> None:
    with database.sesion() as db:
        hay = db.execute(select(func.count(CuentaDB.id)).where(CuentaDB.usuario_id == usuario_id)).scalar_one()
        if hay:
            return
        creada_en = _mes_anterior(movimientos.hoy())
        for nombre, tipo, icono, tono, inicial, cupo, dia_pago in _CUENTAS:
            db.add(CuentaDB(usuario_id=usuario_id, nombre=nombre, tipo=tipo, icono=icono, tono=tono,
                            creada_en=creada_en, inicial=Decimal(inicial),
                            cupo=Decimal(cupo) if cupo else None, dia_pago=dia_pago))


def ref_plantilla(nombre: str) -> CuentaRef | None:
    """La cuenta que usa una fila de la plantilla, con su nombre actual. None si se eliminó: esa fila
    no se siembra."""
    cuenta = cuentas.obtener(USUARIO_PRUEBA_ID, _IDS_CUENTAS[nombre])
    return cuentas.ref(cuenta) if cuenta else None


def _movimientos_del_mes(db, usuario_id: int, primero: date, siguiente: date) -> int:
    return db.execute(
        select(func.count(MovimientoDB.id)).where(
            MovimientoDB.usuario_id == usuario_id,
            MovimientoDB.fecha >= primero, MovimientoDB.fecha < siguiente,
        )
    ).scalar_one()


def _sembrar_mes(usuario_id: int, anio: int, mes: int) -> None:
    """La plantilla del mes, solo si el mes está vacío y solo hasta hoy()."""
    primero = date(anio, mes, 1)
    siguiente = date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)
    with database.sesion() as db:
        if _movimientos_del_mes(db, usuario_id, primero, siguiente):
            return
    limite = movimientos.hoy()
    ultimo = movimientos._ultimo_dia(anio, mes)
    # De la más vieja a la más nueva, para que los ids crezcan con la fecha. Las cuentas se resuelven
    # fuera de la transacción: puede crearlas si la tabla está vacía.
    filas = []
    for dia, descripcion, nombre_categoria, nombre_cuenta, tipo, monto in reversed(_MOVIMIENTOS):
        fecha = date(anio, mes, min(dia, ultimo))
        ref_cuenta = ref_plantilla(nombre_cuenta)
        if fecha > limite or ref_cuenta is None:
            continue
        categoria_id = categorias.predeterminada(nombre_categoria).id
        filas.append((ref_cuenta.id, categoria_id, tipo, Decimal(monto), fecha, descripcion))
    if not filas:
        return
    with database.sesion() as db:
        if _movimientos_del_mes(db, usuario_id, primero, siguiente):
            return
        for cuenta_id, categoria_id, tipo, monto, fecha, descripcion in filas:
            db.add(MovimientoDB(usuario_id=usuario_id, cuenta_id=cuenta_id, categoria_id=categoria_id,
                                tipo=tipo, monto=monto, fecha=fecha, descripcion=descripcion))


def _sembrar_presupuesto(usuario_id: int, anio: int, mes: int) -> None:
    """El ejemplo del mes anterior a hoy(), solo si ese mes aún no tiene presupuesto."""
    with database.sesion() as db:
        cuantos = db.execute(
            select(func.count(PresupuestoDB.id)).where(
                PresupuestoDB.usuario_id == usuario_id, PresupuestoDB.anio == anio, PresupuestoDB.mes == mes,
            )
        ).scalar_one()
    if cuantos or (anio, mes) != presupuestos._mes_anterior(movimientos.hoy()):
        return
    ejemplo = [(categorias.predeterminada(nombre).id, Decimal(monto)) for nombre, monto in _PRESUPUESTO.items()]
    with database.sesion() as db:
        for categoria_id, monto in ejemplo:
            db.add(PresupuestoDB(usuario_id=usuario_id, categoria_id=categoria_id, anio=anio, mes=mes,
                                 monto_limite=monto))


def instalar(monkeypatch) -> None:
    """Envuelve los servicios para que siembren al usuario de prueba antes de responder."""
    reiniciar = database.reiniciar
    listar_cuentas = cuentas.listar
    listar_movimientos = movimientos.listar
    desde = movimientos.desde
    guardar = movimientos._guardar
    del_mes = presupuestos.del_mes

    def cuentas_listar(usuario_id, *args, **kwargs):
        if usuario_id == USUARIO_PRUEBA_ID:
            _sembrar_cuentas(usuario_id)
        return listar_cuentas(usuario_id, *args, **kwargs)

    def movimientos_listar(usuario_id, anio, mes, *args, **kwargs):
        if usuario_id == USUARIO_PRUEBA_ID:
            _sembrar_mes(usuario_id, anio, mes)
        return listar_movimientos(usuario_id, anio, mes, *args, **kwargs)

    def movimientos_desde(usuario_id, fecha, *args, **kwargs):
        # Cada mes desde ahí hasta hoy, para que los saldos no dependan de qué meses se hayan visitado.
        if usuario_id == USUARIO_PRUEBA_ID:
            anio, mes, limite = fecha.year, fecha.month, movimientos.hoy()
            while (anio, mes) <= (limite.year, limite.month):
                _sembrar_mes(usuario_id, anio, mes)
                anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
        return desde(usuario_id, fecha, *args, **kwargs)

    def movimientos_guardar(usuario_id, id, entrada, *args, **kwargs):
        # Sembrar el mes de destino antes de guardar, para que una siembra posterior no lo pise.
        if usuario_id == USUARIO_PRUEBA_ID:
            _sembrar_mes(usuario_id, entrada.fecha.year, entrada.fecha.month)
        return guardar(usuario_id, id, entrada, *args, **kwargs)

    def presupuestos_del_mes(usuario_id, anio, mes, *args, **kwargs):
        if usuario_id == USUARIO_PRUEBA_ID:
            _sembrar_presupuesto(usuario_id, anio, mes)
        return del_mes(usuario_id, anio, mes, *args, **kwargs)

    def database_reiniciar():
        # Muchos tests vacían la base al empezar; el usuario de prueba vuelve a existir enseguida
        # (sus cuentas, movimientos y presupuestos lo necesitan por la clave foránea).
        reiniciar()
        crear_usuario()

    monkeypatch.setattr(database, "reiniciar", database_reiniciar)
    monkeypatch.setattr(cuentas, "listar", cuentas_listar)
    monkeypatch.setattr(movimientos, "listar", movimientos_listar)
    monkeypatch.setattr(movimientos, "desde", movimientos_desde)
    monkeypatch.setattr(movimientos, "_guardar", movimientos_guardar)
    monkeypatch.setattr(presupuestos, "del_mes", presupuestos_del_mes)
