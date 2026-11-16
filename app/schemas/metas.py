"""Contrato entre la sección Metas (y la API) y el backend.

Una meta junta plata para algo («Viaje: 2.000.000 para diciembre»). La plata entra con aportes que se
registran en la meta: no sale de ninguna cuenta ni cuenta como gasto. Lo ahorrado es la suma de los
aportes (los retiros restan).
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

# cumplida: ya llegó al objetivo · sin_fecha: no tiene fecha límite · vencida: pasó la fecha sin llegar
# atrasada: lleva menos de lo esperado a hoy · al_dia: va bien
EstadoMeta = Literal["cumplida", "sin_fecha", "vencida", "atrasada", "al_dia"]


class Meta(BaseModel):
    id: int
    nombre: str
    objetivo: Decimal
    fecha_limite: date | None
    creada_en: date


class Aporte(BaseModel):
    id: int
    monto: Decimal  # positivo: aporte; negativo: retiro
    fecha: date


class MetaConProgreso(BaseModel):
    meta: Meta
    ahorrado: Decimal
    faltante: Decimal               # nunca negativo
    pct: float                      # topado en 100
    estado: EstadoMeta
    por_mes: Decimal | None         # cuánto guardar cada mes para llegar a la fecha
    meses_restantes: int | None     # del mes actual al de la fecha límite, ambos incluidos
    aportes: list[Aporte]           # del más nuevo al más viejo


class PanelMetas(BaseModel):
    metas: list[MetaConProgreso]    # sin cumplir por fecha límite (sin fecha al final), luego cumplidas
    total_ahorrado: Decimal
    total_objetivo: Decimal


class MetaEntrada(BaseModel):
    """Cuerpo de crear y editar. Las reglas las valida el servicio."""
    nombre: str
    objetivo: Decimal
    fecha_limite: date | None = None


class AporteEntrada(BaseModel):
    """Cuerpo de aportar o retirar: el monto siempre positivo; retiro=True lo resta."""
    monto: Decimal
    fecha: date
    retiro: bool = False
