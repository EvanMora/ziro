"""Modelo SQLAlchemy para la tabla de usuarios."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

__all__ = ["Base", "Usuario", "UsuarioDB"]


class UsuarioDB(Base):
    """Entidad Usuario en SQLite.

    docs/alcance.md:
    Usuario (id, nombre, email, password_hash, creado_en)
    Adicionalmente incluye google_sub y foto_url para soportar inicio de sesión con Google.
    """

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    foto_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


# Alias para conveniencia
Usuario = UsuarioDB
