"""Acceso a la base de datos: SQLite con SQLAlchemy.

Por ahora cubre la tabla de usuarios (quienes se registran con correo y contraseña o entran con
Google). TODO(backend): cuando llegue el almacenamiento real, las demás tablas (Cuenta, Categoria,
Movimiento, ...) se agregan a este módulo o se conectan a la misma base de datos.

La ruta por defecto es data/usuarios.sqlite (carpeta ignorada en .gitignore).
Se puede cambiar mediante la variable de entorno DATABASE_PATH o DATABASE_URL.
"""
from collections.abc import Generator
from contextlib import contextmanager
import os
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import Engine, StaticPool, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

DATABASE_PATH: Any = os.environ.get("DATABASE_PATH", "data/usuarios.sqlite")
_motores: dict[str, tuple[Engine, sessionmaker[Session]]] = {}


def obtener_motor_y_sesion(ruta: Any = None) -> tuple[Engine, sessionmaker[Session]]:
    """Obtiene o inicializa el motor SQLAlchemy y la fábrica de sesiones para la ruta dada."""
    # Lee dinámicamente DATABASE_PATH por si fue modificado en tests (e.g. monkeypatch)
    modulo = sys.modules.get(__name__)
    ruta_val = ruta if ruta is not None else (getattr(modulo, "DATABASE_PATH", None) or DATABASE_PATH)
    ruta_str = str(ruta_val)

    # Soporte para DATABASE_URL completa o ruta a archivo SQLite
    if ruta_str.startswith("sqlite:///"):
        url = ruta_str
        archivo = ruta_str.replace("sqlite:///", "")
    elif "://" in ruta_str:
        url = ruta_str
        archivo = ""
    else:
        url = f"sqlite:///{ruta_str}"
        archivo = ruta_str

    if archivo and archivo != ":memory:":
        Path(archivo).parent.mkdir(parents=True, exist_ok=True)

    if url not in _motores:
        en_memoria = url in ("sqlite:///:memory:", "sqlite://")
        motor = create_engine(
            url,
            connect_args={"check_same_thread": False} if "sqlite" in url else {},
            # En memoria, cada conexión nueva crearía una base VACÍA: comparten una sola.
            poolclass=StaticPool if en_memoria else None,
        )
        fabrica = sessionmaker(autocommit=False, autoflush=False, bind=motor)
        _motores[url] = (motor, fabrica)

        from app.models.usuarios import Base
        Base.metadata.create_all(bind=motor)

    return _motores[url]


def obtener_motor(ruta: Any = None) -> Engine:
    motor, _ = obtener_motor_y_sesion(ruta)
    return motor


def obtener_fabrica_sesion(ruta: Any = None) -> sessionmaker[Session]:
    _, fabrica = obtener_motor_y_sesion(ruta)
    return fabrica


@contextmanager
def sesion(ruta: Any = None) -> Generator[Session, None, None]:
    """Entrega una sesión de SQLAlchemy y gestiona commit/rollback y cierre."""
    _, fabrica = obtener_motor_y_sesion(ruta)
    db = fabrica()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def conexion(ruta: Any = None) -> Generator[Session, None, None]:
    """Alias de sesion() para compatibilidad."""
    with sesion(ruta) as db:
        yield db


def obtener_db() -> Generator[Session, None, None]:
    """Dependencia para inyección de sesiones en FastAPI."""
    with sesion() as db:
        yield db


def reiniciar() -> None:
    """Vacía la tabla de usuarios y reinicia la secuencia autoincrement. Para tests."""
    motor, fabrica = obtener_motor_y_sesion()
    from app.models.usuarios import Base

    Base.metadata.create_all(bind=motor)
    with fabrica() as db:
        db.execute(text("DELETE FROM usuarios"))
        try:
            db.execute(text("DELETE FROM sqlite_sequence WHERE name='usuarios'"))
        except Exception:
            # sqlite_sequence solo existe si ya hubo autoincrement
            pass
        db.commit()
