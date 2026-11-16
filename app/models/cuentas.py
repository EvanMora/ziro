"""Modelo SQLAlchemy para la tabla de cuentas."""
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

MAX_NOMBRE = 40

# Tipos: ahorros|corriente|billetera|efectivo|tarjeta (ver app/schemas/cuentas.py)
TIPO_TARJETA = "tarjeta"


class CuentaDB(Base):
    """Una cuenta de dinero (ahorros, corriente, billetera, efectivo) o una tarjeta de crédito.

    docs/alcance.md: Cuenta (id, usuario_id, nombre, tipo, saldo_inicial).

    "inicial" es el saldo (o la deuda de la tarjeta) el día de `creada_en`; puede ser negativo:
    editar el saldo de hoy ajusta el punto de partida por la diferencia. Numeric, nunca float.
    Se puede guardar más de lo que acepta hasta MAX_MONTO (10^12): el tope del monto es
    exclusivo, así que el máximo tiene 12 dígitos enteros y hacen falta 14 de precisión.
    cupo y dia_pago solo aplican a las tarjetas (null en las demás).
    """

    __tablename__ = "cuentas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(MAX_NOMBRE), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    icono: Mapped[str] = mapped_column(String(20), nullable=False)
    tono: Mapped[str] = mapped_column(String(20), nullable=False)
    creada_en: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    inicial: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cupo: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    dia_pago: Mapped[int | None] = mapped_column(Integer, nullable=True)  # día del mes, 1-31


# Alias para conveniencia
Cuenta = CuentaDB
