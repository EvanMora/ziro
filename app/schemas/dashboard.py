"""Contrato entre la pantalla de Resumen y el backend.

La plantilla solo conoce estos modelos. Mientras no existan las tablas, services/dashboard.py
devuelve datos de prueba con esta misma forma; cuando estén, se cambian las consultas y la
pantalla no se toca.

Todo el dinero va en Decimal (nunca float) y sin formato: el formato lo pone la plantilla.
"""
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.movimientos import Movimiento


class CuentaSaldo(BaseModel):
    nombre: str
    tipo: str
    saldo: Decimal


class GastoCategoria(BaseModel):
    categoria: str
    total: Decimal


class ResumenDashboard(BaseModel):
    anio: int
    mes: int
    saldo_total: Decimal                            # suma del saldo de las cuentas de dinero (sin tarjetas)
    cuentas: list[CuentaSaldo]                      # solo las de dinero
    deuda_tarjetas: Decimal                         # suma de lo que se debe en tarjetas de crédito
    ingresos_mes: Decimal
    gastos_mes: Decimal
    gastos_por_categoria: list[GastoCategoria]      # solo gastos del mes, de mayor a menor
    movimientos_recientes: list[Movimiento]  # los últimos del mes, del más nuevo al más viejo
