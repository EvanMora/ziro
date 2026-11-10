"""Reglas de las cuentas: saldos reales desde creada_en, tarjetas con cupo, deuda y fecha límite,
nombre único, grupo fijo con movimientos y eliminación que pasa los movimientos a otra cuenta."""
from datetime import date
from decimal import Decimal

import pytest

from app.schemas.cuentas import CuentaEntrada
from app.schemas.movimientos import MovimientoEntrada
from app.services import cuentas, movimientos
from app.services.comun import ErrorValidacion, NoEncontrado

U = 1


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 11, 15))


def entrada(nombre="Nequi", tipo="billetera", saldo="200000", **cambios):
    datos = {"nombre": nombre, "tipo": tipo, "icono": "celular", "tono": "ciruela", "saldo": Decimal(saldo)}
    if tipo == "tarjeta":
        datos |= {"icono": "tarjeta", "cupo": Decimal("3000000"), "dia_pago": 20}
    return CuentaEntrada(**(datos | cambios))


def gasto(cuenta_id, monto="50000", fecha=date(2026, 11, 14), tipo="gasto"):
    categoria = 3 if tipo == "gasto" else 2
    return movimientos.crear(U, MovimientoEntrada(tipo=tipo, monto=Decimal(monto), categoria_id=categoria,
                                                  cuenta_id=cuenta_id, fecha=fecha))


def saldo(id, usuario=U):
    p = cuentas.panel(usuario)
    return next(c.saldo for c in [*p.dinero, *p.tarjetas] if c.cuenta.id == id)


def errores(funcion, *args, **kwargs):
    with pytest.raises(ErrorValidacion) as e:
        funcion(*args, **kwargs)
    return e.value.errores


# ---------- Cuentas de prueba y saldos ----------

def test_cuentas_de_prueba_y_saldos():
    p = cuentas.panel(U)

    assert [(c.cuenta.nombre, c.saldo) for c in p.dinero] == [
        ("Cuenta de ahorros", Decimal("3612400")),
        ("Billetera digital", Decimal("525000")),
        ("Efectivo", Decimal("245500")),
    ]
    assert p.tienes == Decimal("4382900")
    [t] = p.tarjetas
    assert t.cuenta.nombre == "Tarjeta de crédito"
    assert (t.saldo, t.disponible) == (Decimal("840000"), Decimal("2160000"))
    assert (t.fecha_limite, t.dias_para_pagar) == (date(2026, 11, 15), 0)
    assert p.debes == Decimal("840000")
    assert p.te_queda == Decimal("3542900")


def _cifras(p):
    return [(c.cuenta.id, c.saldo, c.disponible) for c in [*p.dinero, *p.tarjetas]], p.tienes, p.debes


def test_saldo_no_depende_de_meses_visitados():
    antes = _cifras(cuentas.panel(U))
    cuentas.reiniciar()
    movimientos.reiniciar()
    movimientos.listar(U, 2026, 3)
    movimientos.listar(U, 2026, 10)

    assert _cifras(cuentas.panel(U)) == antes


def test_solo_cuentan_movimientos_desde_creada_en():
    gasto(1, fecha=date(2026, 9, 20))
    assert saldo(1) == Decimal("3612400")

    gasto(1)
    assert saldo(1) == Decimal("3562400")


def test_gasto_con_tarjeta_sube_la_deuda_e_ingreso_la_baja():
    tienes = cuentas.panel(U).tienes
    gasto(4, monto="100000")
    assert saldo(4) == Decimal("940000")

    gasto(4, monto="40000", tipo="ingreso")
    assert saldo(4) == Decimal("900000")
    assert cuentas.panel(U).tienes == tienes


def test_crear_dinero_y_tarjeta():
    nequi = cuentas.crear(U, entrada())
    nu = cuentas.crear(U, entrada("Tarjeta Nu", "tarjeta", saldo="500000"))

    assert nequi.creada_en == nu.creada_en == date(2026, 11, 15)
    assert (nequi.cupo, nequi.dia_pago) == (None, None)
    assert saldo(nequi.id) == Decimal("200000")
    assert saldo(nu.id) == Decimal("500000")
    nombres = [c.nombre for c in movimientos.catalogo(U)[0]]
    assert "Nequi" in nombres and "Tarjeta Nu" in nombres


@pytest.mark.parametrize(
    ("cambios", "esperado"),
    [
        ({"nombre": ""}, {"nombre": "Escribe un nombre."}),
        ({"nombre": "x" * 41}, {"nombre": "Máximo 40 caracteres."}),
        ({"nombre": " efectivo "}, {"nombre": "Ya tienes una cuenta con ese nombre."}),
        ({"saldo": Decimal(-1)}, {"saldo": "Escribe un saldo de 0 o más."}),
        ({"tipo": "tarjeta", "saldo": Decimal(-1)}, {"saldo": "Escribe una deuda de 0 o más."}),
        ({"tipo": "tarjeta", "cupo": None}, {"cupo": "Escribe un cupo mayor que 0."}),
        ({"tipo": "tarjeta", "cupo": Decimal(0)}, {"cupo": "Escribe un cupo mayor que 0."}),
        ({"tipo": "tarjeta", "dia_pago": 0}, {"dia_pago": "Elige un día entre 1 y 31."}),
        ({"tipo": "tarjeta", "dia_pago": 32}, {"dia_pago": "Elige un día entre 1 y 31."}),
        ({"tipo": "tarjeta", "dia_pago": None}, {"dia_pago": "Elige un día entre 1 y 31."}),
        ({"saldo": Decimal("1000000000000")}, {"saldo": "El monto es demasiado grande."}),
        ({"tipo": "tarjeta", "cupo": Decimal("1000000000000")}, {"cupo": "El monto es demasiado grande."}),
        ({"tipo": "tarjeta", "cupo": Decimal("0.001")}, {"cupo": "Escribe un cupo mayor que 0."}),
    ],
)
def test_validaciones(cambios, esperado):
    assert errores(cuentas.crear, U, _entrada_con(cambios)) == esperado


@pytest.mark.parametrize(
    "cambios",
    [
        {"nombre": "x" * 40},
        {"saldo": Decimal(0)},
        {"saldo": Decimal("999999999999.99")},
        {"tipo": "tarjeta", "cupo": Decimal("0.01")},
        {"tipo": "tarjeta", "cupo": Decimal(1)},
        {"tipo": "tarjeta", "dia_pago": 1},
        {"tipo": "tarjeta", "dia_pago": 31},
    ],
)
def test_valores_en_el_limite_se_aceptan(cambios):
    e = _entrada_con(cambios)
    assert cuentas.crear(U, e).tipo == e.tipo


def _entrada_con(cambios: dict) -> CuentaEntrada:
    """Entrada base del tipo pedido con los cambios aplicados. No modifica `cambios`: es el dict
    del parametrize y pytest lo reusa si la suite corre más de una vez en el mismo proceso."""
    tipo = cambios.get("tipo", "billetera")
    return entrada(tipo=tipo).model_copy(update={k: v for k, v in cambios.items() if k != "tipo"})


@pytest.mark.parametrize(
    ("hoy", "esperado"),
    [(date(2027, 1, 10), date(2026, 12, 1)), (date(2026, 11, 15), date(2026, 10, 1))],
)
def test_mes_anterior_cruza_el_anio_en_enero(hoy, esperado):
    assert cuentas._mes_anterior(hoy) == esperado


def test_maximo_de_cuentas(monkeypatch):
    monkeypatch.setattr(cuentas, "MAX_CUENTAS", 5)
    cuentas.crear(U, entrada())

    assert errores(cuentas.crear, U, entrada("Otra")) == {"general": "Llegaste al máximo de 5 cuentas."}


# ---------- Editar ----------

def test_editar_ajusta_el_saldo_de_hoy():
    cuentas.actualizar(U, 1, entrada("Cuenta de ahorros", "ahorros", saldo="3000000", icono="banco"))
    assert saldo(1) == Decimal("3000000")

    gasto(1, monto="100000")
    assert saldo(1) == Decimal("2900000")


def test_renombrar_cambia_movimientos_y_meses_nuevos():
    movimientos.listar(U, 2026, 10)
    cuentas.actualizar(U, 1, entrada("Ahorros Banco X", "ahorros", saldo="3612400", icono="banco"))

    for mes in (10, 5):
        lista = movimientos.listar(U, 2026, mes).movimientos
        assert {m.cuenta.nombre for m in lista if m.cuenta.id == 1} == {"Ahorros Banco X"}


def test_grupo_fijo_con_movimientos():
    assert errores(cuentas.actualizar, U, 1, entrada("Cuenta de ahorros", "tarjeta")) == {
        "tipo": "Ya tiene movimientos: no puede pasar de dinero a tarjeta ni al revés."}

    assert cuentas.actualizar(U, 1, entrada("Cuenta de ahorros", "corriente")).tipo == "corriente"


def test_editar_inexistente():
    with pytest.raises(NoEncontrado):
        cuentas.actualizar(U, 999, entrada())


# ---------- Eliminar ----------

def test_eliminar_sin_usos():
    nequi = cuentas.crear(U, entrada())

    cuentas.eliminar(U, nequi.id)

    assert cuentas.obtener(U, nequi.id) is None
    with pytest.raises(NoEncontrado):
        cuentas.eliminar(U, nequi.id)


def test_eliminar_con_usos_pide_destino():
    mensaje = errores(cuentas.eliminar, U, 1)["mover_a"]

    assert mensaje.startswith("Tiene ") and mensaje.endswith("Elige a qué cuenta pasarlos.")


@pytest.mark.parametrize(("destino", "mensaje"), [
    (4, "Elige una cuenta de dinero."),
    (999, "Elige otra cuenta."),
    (1, "Elige otra cuenta."),
])
def test_eliminar_con_destino_invalido(destino, mensaje):
    assert errores(cuentas.eliminar, U, 1, destino) == {"mover_a": mensaje}


def test_eliminar_pasa_los_movimientos():
    m = gasto(1)

    cuentas.eliminar(U, 1, mover_a=3)

    assert cuentas.obtener(U, 1) is None
    assert movimientos.obtener(U, m.id).cuenta.model_dump() == {"id": 3, "nombre": "Efectivo"}


def test_no_se_elimina_la_unica_tarjeta_con_usos():
    gasto(4)

    assert errores(cuentas.eliminar, U, 4, 1) == {
        "mover_a": "Es tu única tarjeta. Crea otra para pasarle sus movimientos antes de eliminarla."}


def test_eliminar_cuenta_de_plantilla_y_sembrar_otro_mes():
    cuentas.eliminar(U, 3, mover_a=2)

    lista = movimientos.listar(U, 2026, 4).movimientos
    assert lista and all(m.cuenta.id != 3 for m in lista)


# ---------- Fecha límite y orden ----------

@pytest.mark.parametrize(("dia", "hoy", "esperada"), [
    (15, date(2026, 11, 15), date(2026, 11, 15)),
    (15, date(2026, 11, 16), date(2026, 12, 15)),
    (31, date(2027, 2, 10), date(2027, 2, 28)),
    (10, date(2026, 12, 20), date(2027, 1, 10)),
    (31, date(2026, 4, 30), date(2026, 4, 30)),
])
def test_proxima_fecha_pago(dia, hoy, esperada):
    assert cuentas.proxima_fecha_pago(dia, hoy) == esperada


def test_tarjetas_por_fecha_limite():
    cuentas.crear(U, entrada("Visa", "tarjeta", dia_pago=20))
    cuentas.crear(U, entrada("Master", "tarjeta", dia_pago=16))

    assert [t.cuenta.nombre for t in cuentas.panel(U).tarjetas] == ["Tarjeta de crédito", "Master", "Visa"]


def test_cuentas_por_usuario():
    p = cuentas.panel(2)

    assert (p.dinero, p.tarjetas, p.tienes) == ([], [], Decimal(0))
    nequi = cuentas.crear(2, entrada())
    assert cuentas.obtener(U, nequi.id) is None


def test_editar_sin_saldo_no_toca_el_saldo():
    """El diálogo no manda el saldo si la persona no lo cambió: un gasto registrado mientras la
    página estaba abierta no se pierde al renombrar."""
    gasto(1)

    cuentas.actualizar(U, 1, entrada("Ahorros", "ahorros", icono="banco").model_copy(update={"saldo": None}))

    assert saldo(1) == Decimal("3562400")
    assert errores(cuentas.crear, U, entrada().model_copy(update={"saldo": None})) == {
        "saldo": "Escribe un saldo de 0 o más."}
