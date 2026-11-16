"""Pagos de tarjeta: bajan la deuda y el saldo de la cuenta de origen sin contar como gasto."""
from datetime import date
from decimal import Decimal

import pytest

from app.schemas.cuentas import CuentaEntrada, PagoEntrada
from app.schemas.movimientos import FiltrosMovimientos, MovimientoEntrada
from app.services import cuentas, movimientos
from app.services.comun import ErrorValidacion, NoEncontrado

U = 1
HOY = date(2026, 11, 15)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: HOY)


def pago(monto, origen=1, fecha=date(2026, 11, 12)):
    return PagoEntrada(monto=Decimal(monto), cuenta_origen_id=origen, fecha=fecha)


def saldo(id):
    p = cuentas.panel(U)
    return next(c.saldo for c in [*p.dinero, *p.tarjetas] if c.cuenta.id == id)


def errores(funcion, *args):
    with pytest.raises(ErrorValidacion) as e:
        funcion(*args)
    return e.value.errores


def test_pago_baja_deuda_y_saldo_y_no_es_gasto():
    gastos = movimientos.listar(U, 2026, 11).gastos

    p = cuentas.registrar_pago(U, 4, pago("300000"))

    assert (p.tarjeta.nombre, p.origen.nombre, p.monto) == ("Tarjeta de crédito", "Cuenta de ahorros", Decimal("300000"))
    assert (p.tarjeta_icono, p.tarjeta_tono) == ("tarjeta", "violeta")
    assert saldo(4) == Decimal("540000")
    assert saldo(1) == Decimal("3312400")
    assert cuentas.panel(U).tienes == Decimal("4082900")
    assert movimientos.listar(U, 2026, 11).gastos == gastos


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (pago("0"), {"monto": "Escribe un monto mayor que 0."}),
        (pago("900000"), {"monto": "No puedes pagar más de lo que debes ($840.000)."}),
        (pago("1000000000000"), {"monto": "El monto es demasiado grande."}),
        (pago("1000", origen=4), {"cuenta_origen_id": "Elige de qué cuenta sale el pago."}),
        (pago("1000", origen=999), {"cuenta_origen_id": "Elige de qué cuenta sale el pago."}),
        (pago("300000", origen=3), {"cuenta_origen_id": "No te alcanza: Efectivo tiene $245.500."}),
        (pago("1000", fecha=date(2026, 11, 16)), {"fecha": "La fecha no puede ser futura."}),
        (pago("1000", fecha=date(2026, 9, 30)), {"fecha": "La fecha es anterior a la creación de la cuenta."}),
        (pago("0.001"), {"monto": "Escribe un monto mayor que 0."}),
        # El día de creación de la tarjeta ya cuenta: la deuda se revisa.
        (pago("900000", fecha=date(2026, 10, 1)), {"monto": "No puedes pagar más de lo que debes ($840.000)."}),
    ],
)
def test_reglas_del_pago(entrada, esperado):
    assert errores(cuentas.registrar_pago, U, 4, entrada) == esperado


@pytest.mark.parametrize(
    "entrada",
    [
        pago("0.01"),
        pago("1"),
        pago("840000"),  # exactamente la deuda
        pago("1000", fecha=date(2026, 10, 1)),  # el día en que se creó la tarjeta
        pago("1000", fecha=HOY),
    ],
)
def test_pago_en_los_limites_se_acepta(entrada):
    assert cuentas.registrar_pago(U, 4, entrada).monto == entrada.monto


def test_pago_a_cuenta_de_dinero_o_inexistente():
    assert errores(cuentas.registrar_pago, U, 1, pago("1000")) == {
        "general": "Solo se le pueden registrar pagos a una tarjeta."}
    with pytest.raises(NoEncontrado):
        cuentas.registrar_pago(U, 999, pago("1000"))


def test_editar_pago_hasta_el_total():
    p = cuentas.registrar_pago(U, 4, pago("800000"))

    cuentas.actualizar_pago(U, p.id, pago("840000"))

    assert saldo(4) == Decimal(0)


def test_editar_pago_sin_contar_dos_veces_el_saldo_de_origen():
    p = cuentas.registrar_pago(U, 4, pago("245500", origen=3))

    editado = cuentas.actualizar_pago(U, p.id, pago("245500", origen=3, fecha=date(2026, 11, 13)))

    assert editado.fecha == date(2026, 11, 13)
    assert saldo(3) == Decimal(0)


def test_eliminar_pago_restaura_saldos():
    p = cuentas.registrar_pago(U, 4, pago("300000"))

    cuentas.eliminar_pago(U, p.id)

    assert (saldo(4), saldo(1)) == (Decimal("840000"), Decimal("3612400"))
    assert cuentas.obtener_pago(U, p.id) is None
    with pytest.raises(NoEncontrado):
        cuentas.eliminar_pago(U, p.id)


def test_renombrar_tarjeta_se_ve_en_el_pago():
    p = cuentas.registrar_pago(U, 4, pago("1000"))

    cuentas.actualizar(U, 4, CuentaEntrada(nombre="Tarjeta Nu", tipo="tarjeta", icono="tarjeta", tono="indigo",
                                           saldo=Decimal("839000"), cupo=Decimal("3000000"), dia_pago=15))

    leido = cuentas.obtener_pago(U, p.id)
    assert (leido.tarjeta.nombre, leido.tarjeta_tono) == ("Tarjeta Nu", "indigo")


@pytest.mark.parametrize(("filtros", "cuantos"), [
    (FiltrosMovimientos(), 1),
    (FiltrosMovimientos(tipo="gasto"), 0),
    (FiltrosMovimientos(tipo="ingreso"), 0),
    (FiltrosMovimientos(categoria_id=3), 0),
    (FiltrosMovimientos(cuenta_id=4), 1),
    (FiltrosMovimientos(cuenta_id=1), 1),
    (FiltrosMovimientos(cuenta_id=2), 0),
    (FiltrosMovimientos(q="PAGO"), 1),
    (FiltrosMovimientos(q="credito"), 1),
    (FiltrosMovimientos(q="taxi"), 0),
])
def test_pagos_del_mes_con_filtros(filtros, cuantos):
    cuentas.registrar_pago(U, 4, pago("1000"))

    assert len(cuentas.pagos_del_mes(U, 2026, 11, filtros)) == cuantos
    assert cuentas.pagos_del_mes(U, 2026, 10, FiltrosMovimientos()) == []


def test_usos_incluyen_pagos_y_eliminar_los_mueve():
    nequi = cuentas.crear(U, CuentaEntrada(nombre="Nequi", tipo="billetera", icono="celular", tono="ciruela",
                                           saldo=Decimal("500000")))
    p = cuentas.registrar_pago(U, 4, pago("100000", origen=nequi.id, fecha=HOY))

    assert "mover_a" in errores(cuentas.eliminar, U, nequi.id)
    cuentas.eliminar(U, nequi.id, mover_a=2)
    assert cuentas.obtener_pago(U, p.id).origen.id == 2

    otra = cuentas.crear(U, CuentaEntrada(nombre="Visa", tipo="tarjeta", icono="tarjeta", tono="azul",
                                          saldo=Decimal(0), cupo=Decimal("1000000"), dia_pago=5))
    cuentas.eliminar(U, 4, mover_a=otra.id)
    assert cuentas.obtener_pago(U, p.id).tarjeta.id == otra.id


def test_pago_pasado_a_una_tarjeta_mas_nueva_se_puede_editar(monkeypatch):
    p = cuentas.registrar_pago(U, 4, pago("300000", fecha=date(2026, 11, 1)))
    visa = cuentas.crear(U, CuentaEntrada(nombre="Visa", tipo="tarjeta", icono="tarjeta", tono="azul",
                                          saldo=Decimal(0), cupo=Decimal("1000000"), dia_pago=5))
    cuentas.eliminar(U, 4, mover_a=visa.id)

    editado = cuentas.actualizar_pago(U, p.id, pago("200000", fecha=date(2026, 11, 1)))

    assert editado.monto == Decimal("200000")
    assert saldo(visa.id) == Decimal(0)          # fecha anterior a Visa: no cambia su deuda
    assert saldo(1) == Decimal("3412400")        # pero sí el saldo de origen
    assert errores(cuentas.actualizar_pago, U, p.id, pago("200000", fecha=date(2026, 11, 2))) == {
        "fecha": "La fecha es anterior a la creación de la cuenta."}


def test_mensaje_de_eliminar_separa_movimientos_y_pagos():
    nequi = cuentas.crear(U, CuentaEntrada(nombre="Nequi", tipo="billetera", icono="celular", tono="ciruela",
                                           saldo=Decimal("500000")))
    cuentas.registrar_pago(U, 4, pago("1000", origen=nequi.id, fecha=HOY))
    assert errores(cuentas.eliminar, U, nequi.id) == {"mover_a": "Tiene 1 pago. Elige a qué cuenta pasarlo."}

    movimientos.crear(U, MovimientoEntrada(tipo="gasto", monto=Decimal("2000"), categoria_id=3, cuenta_id=nequi.id,
                                           fecha=HOY))
    assert errores(cuentas.eliminar, U, nequi.id) == {
        "mover_a": "Tiene 1 movimiento y 1 pago. Elige a qué cuenta pasarlos."}


def test_el_panel_cuenta_los_pagos_aparte():
    cuentas.registrar_pago(U, 4, pago("1000"))

    tarjeta = cuentas.panel(U).tarjetas[0]

    assert tarjeta.pagos == 1 and tarjeta.usos == 1
