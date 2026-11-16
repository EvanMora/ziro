"""Modelo SQLAlchemy para la tabla de pagos de tarjeta."""
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PagoTarjetaDB(Base):
    """Un pago hecho a una tarjeta de crédito desde una cuenta de dinero.

    No es un movimiento: la compra ya se contó al pagar con la tarjeta, así que no suma en
    ingresos ni gastos. Baja la deuda de la tarjeta y el saldo de la cuenta de origen (cada
    uno desde su creada_en).
    """

    __tablename__ = "pagos_tarjeta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id"), nullable=False, index=True
    )
    tarjeta_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cuentas.id"), nullable=False, index=True
    )
    origen_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cuentas.id"), nullable=False, index=True
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        # Los pagos del mes y los que tocan cada cuenta en un análisis de usos.
        Index("ix_pagos_usuario_fecha", "usuario_id", "fecha"),
    )


# Alias para conveniencia
PagoTarjeta = PagoTarjetaDB
