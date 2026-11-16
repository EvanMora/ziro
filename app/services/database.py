"""Acceso a la base de datos: SQLite con SQLAlchemy.

Aquí se crea (create_all) el esquema completo de las tablas declaradas en app/models/. Todos los
servicios leen y escriben en esta base, siempre filtrando por usuario_id.

SQLite no revisa las claves foráneas si no se le pide en cada conexión: _activar_claves_foraneas lo
hace, así una fila nunca apunta a un usuario, una cuenta o una categoría que no existe.

La ruta por defecto es data/usuarios.sqlite (carpeta ignorada en .gitignore).
Se puede cambiar mediante la variable de entorno DATABASE_PATH o DATABASE_URL.
"""
from collections.abc import Generator
from contextlib import contextmanager
import os
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import Engine, StaticPool, create_engine, event, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.models.categorias import CategoriaDB, PREDETERMINADAS

DATABASE_PATH: Any = os.environ.get("DATABASE_PATH", "data/usuarios.sqlite")
_motores: dict[str, tuple[Engine, sessionmaker[Session]]] = {}


def _activar_claves_foraneas(conexion, _registro) -> None:
    cursor = conexion.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


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
        if "sqlite" in url:
            event.listen(motor, "connect", _activar_claves_foraneas)
        fabrica = sessionmaker(autocommit=False, autoflush=False, bind=motor)
        _motores[url] = (motor, fabrica)

        # Importar app.models (no solo usuarios) para que create_all conozca todas las tablas.
        from app.models import Base
        Base.metadata.create_all(bind=motor)
        with fabrica() as db:
            _sembrar_predeterminadas(db)
            db.commit()

    return _motores[url]


def _sembrar_predeterminadas(db: Session) -> None:
    """Inserta las 7 categorías predeterminadas (ids 1-7) si la tabla no tiene ninguna.

    Es la siembra básica del sistema: sin ellas la app no puede registrar movimientos. Solo se
    siembra si no hay ninguna predeterminada, así los reinicios de tests no duplican."""
    hay = db.execute(
        select(func.count(CategoriaDB.id)).where(CategoriaDB.usuario_id.is_(None))
    ).scalar_one()
    if hay:
        return
    db.add_all([
        CategoriaDB(id=id_, nombre=nombre, tipo=tipo, usuario_id=None)
        for id_, nombre, tipo in PREDETERMINADAS
    ])


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
    """Vacía todas las tablas, reinicia las secuencias autoincrement y vuelve a sembrar las
    categorías predeterminadas. Para tests."""
    motor, fabrica = obtener_motor_y_sesion()
    from app.models import Base

    Base.metadata.create_all(bind=motor)
    tablas = ("movimientos", "pagos_tarjeta", "presupuestos", "cuentas", "categorias", "usuarios")
    with fabrica() as db:
        for tabla in tablas:
            db.execute(text(f"DELETE FROM {tabla}"))
        for tabla in tablas:
            try:
                db.execute(text(f"DELETE FROM sqlite_sequence WHERE name='{tabla}'"))
            except Exception:
                # sqlite_sequence solo existe si ya hubo autoincrement
                pass
        _sembrar_predeterminadas(db)
        db.commit()
