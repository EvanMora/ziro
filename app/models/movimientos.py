"""Modelo SQLAlchemy para la tabla de movimientos."""
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

MAX_DESCRIPCION = 80


class MovimientoDB(Base):
    """Un ingreso o gasto de una cuenta en una categoría.

    docs/alcance.md: Movimiento (id, usuario_id, cuenta_id, categoria_id, tipo, monto, fecha,
    nota). El dinero se guarda como Decimal (Numeric), nunca como float; el monto es siempre
    positivo y el tipo dice si suma o resta.

    Los nombres de cuenta y categoría no se copian aquí: se leen por las claves foráneas, así
    que renombrar no obliga a tocar los movimientos.
    """

    __tablename__ = "movimientos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id"), nullable=False, index=True
    )
    cuenta_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cuentas.id"), nullable=False, index=True
    )
    categoria_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("categorias.id"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)  # ingreso|gasto
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    descripcion: Mapped[str] = mapped_column(String(MAX_DESCRIPCION), nullable=False, default="")

    __table_args__ = (
        # La mitad de las consultas: los movimientos de un usuario desde una fecha, y del mes.
        Index("ix_movimientos_usuario_fecha", "usuario_id", "fecha"),
    )


# Alias para conveniencia
Movimiento = MovimientoDB
