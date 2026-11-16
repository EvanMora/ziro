"""Contrato entre la sección Cuentas (y la API) y el backend.

Hay dos grupos de cuentas:
- Dinero (ahorros, corriente, billetera, efectivo): su saldo es lo que tienes.
- Tarjetas de crédito: su "saldo" es lo que debes; tienen cupo y día límite de pago.

"inicial" es el saldo (o la deuda) el día de creada_en. Desde ese día cuentan los movimientos:
lo que había antes ya estaba incluido en lo que la persona escribió al crear la cuenta.

Los movimientos siguen usando CuentaRef (app/schemas/movimientos.py).
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, StrictInt

from app.schemas.movimientos import CuentaRef

TipoCuenta = Literal["ahorros", "corriente", "billetera", "efectivo", "tarjeta"]
Icono = Literal["banco", "alcancia", "billetera", "celular", "billetes", "tarjeta", "monedas", "maletin"]
Tono = Literal["azul", "indigo", "violeta", "ciruela", "petroleo", "cafe", "arena", "grafito"]

NOMBRE_TIPO = {
    "ahorros": "Cuenta de ahorros",
    "corriente": "Cuenta corriente",
    "billetera": "Billetera digital",
    "efectivo": "Efectivo",
    "tarjeta": "Tarjeta de crédito",
}


class Cuenta(BaseModel):
    id: int
    nombre: str
    tipo: TipoCuenta
    icono: Icono
    tono: Tono
    creada_en: date
    inicial: Decimal            # saldo (dinero) o deuda (tarjeta) el día de creada_en
    cupo: Decimal | None        # solo tarjetas
    dia_pago: int | None        # solo tarjetas: día del mes, de 1 a 31


class CuentaEntrada(BaseModel):
    """Cuerpo de crear y editar. "saldo" es el saldo (o la deuda) de HOY: al editar, cambiarlo
    corrige el punto de partida. Al editar, null (o sin saldo) deja el saldo como está: así un
    movimiento registrado mientras el diálogo estaba abierto no se pierde al renombrar. Las reglas
    las valida el servicio."""
    nombre: str
    tipo: TipoCuenta
    icono: Icono
    tono: Tono
    saldo: Decimal | None = None
    cupo: Decimal | None = None
    dia_pago: StrictInt | None = None  # estricto: true no cuenta como el día 1


class CuentaConSaldo(BaseModel):
    cuenta: Cuenta
    saldo: Decimal                  # en las tarjetas, la deuda
    disponible: Decimal | None      # tarjetas: cupo − deuda (negativo si se pasó del cupo)
    fecha_limite: date | None       # tarjetas: próxima vez que llega dia_pago
    dias_para_pagar: int | None
    usos: int                       # movimientos y pagos: si es > 0, eliminarla pide a dónde pasarlos
    pagos: int                      # cuántos de los usos son pagos de tarjeta


class PanelCuentas(BaseModel):
    dinero: list[CuentaConSaldo]    # en el orden en que se crearon
    tarjetas: list[CuentaConSaldo]  # por fecha límite más cercana, luego por nombre
    tienes: Decimal                 # suma de los saldos de dinero
    debes: Decimal                  # suma de las deudas
    te_queda: Decimal               # tienes − debes


class PagoEntrada(BaseModel):
    """Cuerpo de registrar y editar un pago de tarjeta. La tarjeta va en la URL."""
    monto: Decimal
    cuenta_origen_id: StrictInt  # estricto: true no cuenta como la cuenta 1
    fecha: date


class Pago(BaseModel):
    """Un pago de tarjeta: plata que pasa de una cuenta de dinero a la tarjeta. No es un gasto ni
    un ingreso (la compra ya se contó al pagar con la tarjeta)."""
    id: int
    fecha: date
    monto: Decimal
    tarjeta: CuentaRef
    origen: CuentaRef
    tarjeta_icono: Icono
    tarjeta_tono: Tono
