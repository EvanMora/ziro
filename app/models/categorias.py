"""Modelo SQLAlchemy para la tabla de categorías."""
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

MAX_NOMBRE = 40

# Las 7 categorías predeterminadas del sistema (docs/alcance.md). La base las siembra al crearse
# (o al vaciarse en tests) con estos ids fijos; el catálogo y los tests las esperan en 1-7.
PREDETERMINADAS: tuple[tuple[int, str, str], ...] = (
    (1, "Salario", "ingreso"),
    (2, "Otros ingresos", "ingreso"),
    (3, "Mercado", "gasto"),
    (4, "Transporte", "gasto"),
    (5, "Arriendo", "gasto"),
    (6, "Ocio", "gasto"),
    (7, "Otros gastos", "gasto"),
)


class CategoriaDB(Base):
    """Una categoría de movimiento, propia o predeterminada del sistema.

    docs/alcance.md: Categoria (id, usuario_id | null, nombre, tipo: ingreso|gasto).
    Las predeterminadas (Salario, Otros ingresos, Mercado, Transporte, Arriendo, Ocio y
    Otros gastos) llevan usuario_id NULL, son iguales para todos y no se editan ni se
    eliminan; las propias llevan el id de su dueño.
    """

    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("usuarios.id"), nullable=True, index=True
    )
    nombre: Mapped[str] = mapped_column(String(MAX_NOMBRE), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)  # ingreso|gasto

    @property
    def predeterminada(self) -> bool:
        return self.usuario_id is None


# Alias para conveniencia
Categoria = CategoriaDB
