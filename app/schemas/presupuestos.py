"""Contrato entre la sección Presupuestos (y la API) y el backend.

Un presupuesto es de un mes: se crea cada mes, con un monto por categoría de gasto. La suma de
esos montos es el presupuesto del mes. Lo gastado sale de los movimientos de gasto de esas
categorías en el mes; los gastos de categorías sin presupuesto no lo consumen.

Estados de una categoría (y del mes), los mismos de docs/design-system.md:
- "ok": menos del 80 %.
- "alerta": del 80 % al 100 %, incluido. Naranja (--color-warning).
- "excedido": más del 100 %. Rojo (--color-danger).
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.movimientos import CategoriaRef

Estado = Literal["ok", "alerta", "excedido"]


class PresupuestoCategoria(BaseModel):
    categoria: CategoriaRef
    limite: Decimal    # > 0
    gastado: Decimal   # gastos del mes en la categoría
    restante: Decimal  # limite - gastado; negativo si se pasó
    pct: float         # gastado / limite * 100, sin tope
    estado: Estado


class GastoDelDia(BaseModel):
    fecha: date
    total: Decimal  # todos los gastos del día, tengan o no presupuesto
    movimientos: int


class PresupuestoDelMes(BaseModel):
    anio: int
    mes: int
    creado: bool                            # False: el mes aún no tiene presupuesto
    categorias: list[PresupuestoCategoria]  # en el orden del catálogo
    total: Decimal                          # suma de los límites
    gastado: Decimal                        # gastos de las categorías con presupuesto
    restante: Decimal                       # total - gastado; negativo si se pasó
    pct: float
    estado: Estado
    sin_presupuesto: Decimal                # gastos del mes en categorías sin presupuesto
    dias: list[GastoDelDia]                 # cada día del mes, del 1 al último


class MontoCategoria(BaseModel):
    categoria_id: int
    monto: Decimal = Field(decimal_places=2)


class PresupuestoEntrada(BaseModel):
    """Cuerpo de crear y editar el presupuesto de un mes. Las categorías que no vienen (o vienen
    en 0) quedan sin presupuesto. Las reglas las valida el servicio."""
    montos: list[MontoCategoria]
