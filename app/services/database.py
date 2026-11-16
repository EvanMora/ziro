"""Acceso a la base de datos con SQLAlchemy: SQLite en local y en los tests, Postgres desplegada.

Aquí se crea (create_all) el esquema completo de las tablas declaradas en app/models/. Todos los
servicios leen y escriben en esta base, siempre filtrando por usuario_id.

SQLite no revisa las claves foráneas si no se le pide en cada conexión: _activar_claves_foraneas lo
hace, así una fila nunca apunta a un usuario, una cuenta o una categoría que no existe.

Qué base se usa (url_base_de_datos): la de DATABASE_URL si existe (la que crean Vercel y Neon, un
Postgres); si no, la de DATABASE_PATH (una ruta a un archivo SQLite o una URL); y si no hay ninguna,
data/usuarios.sqlite (carpeta ignorada en .gitignore). En producción DATABASE_URL es obligatoria.
"""
from collections.abc import Generator
from contextlib import contextmanager
import os
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import Engine, StaticPool, create_engine, event, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import es_produccion
from app.models.categorias import CategoriaDB, PREDETERMINADAS

DATABASE_PATH: Any = os.environ.get("DATABASE_PATH", "data/usuarios.sqlite")
_motores: dict[str, tuple[Engine, sessionmaker[Session]]] = {}


def normalizar_url(url: str) -> str:
    """Las URL postgres:// y postgresql:// (como las entrega Neon) pasan al driver psycopg 3. Solo
    cambia el esquema: usuario, contraseña, host y parámetros quedan igual."""
    for esquema in ("postgres://", "postgresql://"):
        if url.startswith(esquema):
            return "postgresql+psycopg://" + url[len(esquema):]
    return url


def es_postgres(url: str) -> bool:
    return url.startswith("postgresql")


def _url_de(ruta: Any) -> str:
    """Una ruta a un archivo SQLite o una URL completa, como URL de SQLAlchemy."""
    texto = str(ruta)
    return normalizar_url(texto) if "://" in texto else f"sqlite:///{texto}"


def url_base_de_datos() -> str:
    """La URL de la base de esta ejecución (ver el orden en el docstring del módulo)."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return normalizar_url(url)
    if es_produccion():
        raise RuntimeError("DATABASE_URL es obligatoria en producción: Vercel no guarda archivos, así que "
                           "SQLite perdería los datos.")
    # DATABASE_PATH se lee del módulo en cada llamada: los tests lo cambian con monkeypatch.
    modulo = sys.modules.get(__name__)
    return _url_de(getattr(modulo, "DATABASE_PATH", None) or DATABASE_PATH)


def _activar_claves_foraneas(conexion, _registro) -> None:
    cursor = conexion.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def obtener_motor_y_sesion(ruta: Any = None) -> tuple[Engine, sessionmaker[Session]]:
    """Obtiene o inicializa el motor SQLAlchemy y la fábrica de sesiones: los de la base de esta
    ejecución (url_base_de_datos) o, si se pasa, los de esa ruta o URL."""
    url = url_base_de_datos() if ruta is None else _url_de(ruta)

    if url not in _motores:
        if es_postgres(url):
            # Neon cierra las conexiones ociosas: se comprueban antes de usarlas y se renuevan
            # cada 5 minutos, para no heredar una conexión muerta de una instancia dormida.
            motor = create_engine(url, pool_pre_ping=True, pool_recycle=300)
        else:
            archivo = url.removeprefix("sqlite:///")
            en_memoria = url in ("sqlite:///:memory:", "sqlite://")
            if url.startswith("sqlite:///") and not en_memoria:
                Path(archivo).parent.mkdir(parents=True, exist_ok=True)
            motor = create_engine(
                url,
                connect_args={"check_same_thread": False},
                # En memoria, cada conexión nueva crearía una base VACÍA: comparten una sola.
                poolclass=StaticPool if en_memoria else None,
            )
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
    tablas = ("aportes_meta", "metas", "movimientos", "pagos_tarjeta", "presupuestos", "cuentas", "categorias",
              "usuarios")
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
