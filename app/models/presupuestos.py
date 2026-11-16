"""Modelo SQLAlchemy para la tabla de presupuestos mensuales por categoría."""
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PresupuestoDB(Base):
    """El límite de gasto de una categoría en un mes. Fase 2 (docs/alcance.md).

    Un presupuesto es de un mes: se crea cada mes con un monto por categoría de gasto. Los
    gastos de categorías sin presupuesto no consumen ninguno. Lo gastado se compara en el
    servicio (regla 50/30/20 no aplica aquí; el porcentaje se calcula en el backend).
    """

    __tablename__ = "presupuestos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id"), nullable=False, index=True
    )
    categoria_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("categorias.id"), nullable=False
    )
    anio: Mapped[int] = mapped_column(Integer, nullable=False)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12
    monto_limite: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "usuario_id", "anio", "mes", "categoria_id", name="uq_presupuesto_mes"
        ),
    )


# Alias para conveniencia
Presupuesto = PresupuestoDB
