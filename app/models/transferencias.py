"""Modelo SQLAlchemy para la tabla de transferencias entre cuentas de dinero."""
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TransferenciaDB(Base):
    """Plata que pasa de una cuenta de dinero (origen) a otra (destino) del mismo usuario.

    docs/alcance.md (Fase 2): Transferencia (id, usuario_id, cuenta_origen_id,
    cuenta_destino_id, monto, fecha).

    No es un movimiento ni un pago de tarjeta: la plata sigue existiendo, solo cambia de
    cuenta. Baja el saldo del origen y sube el del destino (cada uno desde su creada_en) y no
    suma en ingresos ni gastos. Las tarjetas no participan.
    """

    __tablename__ = "transferencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id"), nullable=False, index=True
    )
    cuenta_origen_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cuentas.id"), nullable=False, index=True
    )
    cuenta_destino_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cuentas.id"), nullable=False, index=True
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        # Las transferencias del mes y las que tocan cada cuenta en un análisis de usos.
        Index("ix_transferencias_usuario_fecha", "usuario_id", "fecha"),
    )


# Alias para conveniencia
Transferencia = TransferenciaDB
