"""Contrato entre la sección Categorías (y la API) y el backend.

Hay dos clases de categorías (ver docs/alcance.md):
- Predeterminadas: del sistema, iguales para todos (usuario_id null). No se editan ni se eliminan.
- Propias: las crea cada usuario. Se renombran, cambian de tipo si aún no tienen movimientos y se
  eliminan; si tienen movimientos, primero se pasan a otra categoría del mismo tipo.

Los movimientos siguen usando CategoriaRef (app/schemas/movimientos.py): "predeterminada" solo le
importa a esta sección.
"""
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.movimientos import Tipo


class Categoria(BaseModel):
    id: int
    nombre: str
    tipo: Tipo
    predeterminada: bool


class CategoriaEntrada(BaseModel):
    """Cuerpo de crear y editar. Las reglas (nombre obligatorio y único dentro del tipo, tipo fijo
    si ya hay movimientos) las valida el servicio."""
    nombre: str
    tipo: Tipo


class CategoriaDelMes(BaseModel):
    categoria: Categoria
    total: Decimal    # suma de sus movimientos del mes (0 si no tiene)
    movimientos: int  # cuántos movimientos tiene en el mes
    usos: int         # cuántos movimientos tiene en total: si es > 0, eliminarla pide a dónde pasarlos


class CategoriasDelMes(BaseModel):
    anio: int
    mes: int
    gastos: list[CategoriaDelMes]    # de mayor a menor total; con el mismo total, en el orden del catálogo
    ingresos: list[CategoriaDelMes]
    total_gastos: Decimal
    total_ingresos: Decimal
