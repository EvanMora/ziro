"""Transferencias entre cuentas: mueven plata de una cuenta de dinero a otra sin contar como
ingreso ni gasto."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import delete

from app.models.transferencias import TransferenciaDB
from app.schemas.cuentas import TransferenciaEntrada
from app.services import cuentas, database, movimientos
from app.services.comun import ErrorValidacion, NoEncontrado

U = 1
HOY = date(2026, 11, 15)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: HOY)


@pytest.fixture(autouse=True)
def _transferencias_vacias():
    """La base no sabe de la tabla nueva todavía (database.reiniciar no la borra): se limpia aparte."""
    with database.sesion() as db:
        db.execute(delete(TransferenciaDB))
    yield
    with database.sesion() as db:
        db.execute(delete(TransferenciaDB))


def transferencia(monto, origen=1, destino=3, fecha=date(2026, 11, 12)):
    return TransferenciaEntrada(monto=Decimal(monto), cuenta_origen_id=origen,
                                cuenta_destino_id=destino, fecha=fecha)


def saldo(id):
    p = cuentas.panel(U)
    return next(c.saldo for c in [*p.dinero, *p.tarjetas] if c.cuenta.id == id)


def errores(funcion, *args):
    with pytest.raises(ErrorValidacion) as e:
        funcion(*args)
    return e.value.errores


def test_transferencia_mueve_saldos_y_no_es_gasto():
    gastos = movimientos.listar(U, 2026, 11).gastos
    antes_1, antes_3 = saldo(1), saldo(3)

    t = cuentas.registrar_transferencia(U, transferencia("200000"))

    assert (t.origen.nombre, t.destino.nombre, t.monto) == ("Cuenta de ahorros", "Efectivo", Decimal("200000"))
    assert saldo(1) == antes_1 - Decimal("200000")
    assert saldo(3) == antes_3 + Decimal("200000")
    assert movimientos.listar(U, 2026, 11).gastos == gastos


def test_transferencia_editar_y_eliminar():
    antes_1, antes_3 = saldo(1), saldo(3)

    t = cuentas.registrar_transferencia(U, transferencia("100000"))
    assert saldo(1) == antes_1 - Decimal("100000")
    assert saldo(3) == antes_3 + Decimal("100000")

    cuentas.actualizar_transferencia(U, t.id, transferencia("150000", origen=3, destino=1))

    assert saldo(1) == antes_1 + Decimal("150000")
    assert saldo(3) == antes_3 - Decimal("150000")

    cuentas.eliminar_transferencia(U, t.id)

    assert saldo(1) == antes_1
    assert saldo(3) == antes_3
    assert cuentas.obtener_transferencia(U, t.id) is None
    with pytest.raises(NoEncontrado):
        cuentas.eliminar_transferencia(U, t.id)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (transferencia("0"), {"monto": "Escribe un monto mayor que 0."}),
        (transferencia("0.001"), {"monto": "Escribe un monto mayor que 0."}),
        (transferencia("1000000000000"), {"monto": "El monto es demasiado grande."}),
        (transferencia("1000", origen=4), {"cuenta_origen_id": "Elige una cuenta de dinero de dónde sale."}),
        (transferencia("1000", origen=999), {"cuenta_origen_id": "Elige una cuenta de dinero de dónde sale."}),
        (transferencia("1000", destino=4), {"cuenta_destino_id": "Elige una cuenta de dinero a dónde va."}),
        (transferencia("1000", destino=999), {"cuenta_destino_id": "Elige una cuenta de dinero a dónde va."}),
        (transferencia("1000", origen=2, destino=2), {"cuenta_destino_id": "Las dos cuentas deben ser distintas."}),
        (transferencia("1000", fecha=date(2026, 11, 16)), {"fecha": "La fecha no puede ser futura."}),
    ],
)
def test_reglas_de_la_transferencia(entrada, esperado):
    assert errores(cuentas.registrar_transferencia, U, entrada) == esperado


def test_no_se_puede_transferir_entre_cuentas_de_otro_usuario(monkeypatch):
    from app.services import usuarios
    monkeypatch.setattr(usuarios, "RONDAS_BCRYPT", 4)  # bcrypt rápido en tests
    # El demo (id 1) tiene las cuentas 1-4; el otro usuario no puede tocarlas.
    usuarios.crear(email="evanpro@ziro.com", password="secreta123", nombre="Evan Pro")
    otro = usuarios.crear(email="otro@transferencias.test", password="secreta123", nombre="Otro")

    assert errores(cuentas.registrar_transferencia, otro.id, transferencia("1000", origen=1, destino=2)) == {
        "cuenta_origen_id": "Elige una cuenta de dinero de dónde sale.",
        "cuenta_destino_id": "Elige una cuenta de dinero a dónde va.",
    }
