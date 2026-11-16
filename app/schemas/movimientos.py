"""Contrato entre la sección Movimientos (y la API) y el backend.

La plantilla y la API solo conocen estos modelos. Mientras no existan las tablas,
services/movimientos.py guarda los datos en memoria; cuando estén, se cambian las consultas y
ni la pantalla ni la API se tocan.

Todo el dinero va en Decimal (nunca float), siempre positivo: el tipo dice si suma o resta.
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, StrictInt

Tipo = Literal["ingreso", "gasto"]


class CuentaRef(BaseModel):
    id: int
    nombre: str


class CategoriaRef(BaseModel):
    id: int
    nombre: str
    tipo: Tipo


class Movimiento(BaseModel):
    id: int
    fecha: date
    descripcion: str  # puede ser ""; la plantilla muestra entonces el nombre de la categoría
    categoria: CategoriaRef
    cuenta: CuentaRef
    tipo: Tipo
    monto: Decimal  # siempre > 0


class FiltrosMovimientos(BaseModel):
    tipo: Tipo | None = None
    cuenta_id: int | None = None
    categoria_id: int | None = None
    q: str | None = None


class ListaMovimientos(BaseModel):
    anio: int
    mes: int
    filtros: FiltrosMovimientos
    movimientos: list[Movimiento]  # ya filtrados, del más reciente al más antiguo
    ingresos: Decimal              # de los movimientos filtrados
    gastos: Decimal


class MovimientoEntrada(BaseModel):
    """Cuerpo de crear y editar. Las reglas de negocio (monto > 0, categoría del mismo tipo,
    fecha no futura, descripción corta) las valida el servicio."""
    tipo: Tipo
    monto: Decimal = Field(decimal_places=2)
    categoria_id: StrictInt  # estricto: true no cuenta como 1
    cuenta_id: StrictInt
    fecha: date
    descripcion: str = ""
