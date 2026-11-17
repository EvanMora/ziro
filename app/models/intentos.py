"""Modelo SQLAlchemy de los intentos que cuentan para un límite: login, registro y consultas a la IA
(app/services/limites.py). Viven en la base, no en la memoria del proceso, para que el límite sea el
mismo aunque la app corra en varias instancias."""
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

MAX_CLAVE = 200


class IntentoDB(Base):
    """Un intento de una clave (p. ej. "login:ip:190.1.2.3" o "ia:42") en un momento."""

    __tablename__ = "intentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clave: Mapped[str] = mapped_column(String(MAX_CLAVE), nullable=False)
    momento: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_intentos_clave_momento", "clave", "momento"),
    )
