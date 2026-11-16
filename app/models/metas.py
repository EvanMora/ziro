"""Modelos SQLAlchemy de las metas de ahorro y sus aportes (Fase 2, docs/alcance.md).

docs/alcance.md: MetaAhorro (id, usuario_id, nombre, monto_objetivo, monto_actual, fecha_limite).
El monto_actual no se guarda: es la suma de los aportes (los retiros van en negativo), así nunca se
descuadra con el historial. Los aportes no salen de ninguna cuenta ni son gastos: es plata apartada.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

MAX_NOMBRE = 40


class MetaDB(Base):
    __tablename__ = "metas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(MAX_NOMBRE), nullable=False)
    objetivo: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fecha_limite: Mapped[date | None] = mapped_column(Date, nullable=True)
    creada_en: Mapped[date] = mapped_column(Date, nullable=False)


class AporteMetaDB(Base):
    """Un aporte (monto positivo) o un retiro (negativo) de una meta."""

    __tablename__ = "aportes_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    meta_id: Mapped[int] = mapped_column(Integer, ForeignKey("metas.id"), nullable=False, index=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
