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
from sqlalchemy.exc import IntegrityError
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


def opciones_motor(url: str) -> dict[str, Any]:
    """Las opciones de create_engine para la base de esa URL."""
    if es_postgres(url):
        return {
            # Neon cierra las conexiones ociosas: se comprueban antes de usarlas y se renuevan cada
            # 5 minutos, para no heredar una conexión muerta de una instancia que estuvo dormida.
            "pool_pre_ping": True,
            "pool_recycle": 300,
            # Sin sentencias preparadas del lado del servidor: el pooler de Neon puede dar cada
            # transacción a una conexión distinta, donde la sentencia preparada no existe.
            "connect_args": {"prepare_threshold": None},
        }
    opciones: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
    if url in ("sqlite:///:memory:", "sqlite://"):
        # En memoria, cada conexión nueva crearía una base VACÍA: comparten una sola.
        opciones["poolclass"] = StaticPool
    return opciones


def obtener_motor_y_sesion(ruta: Any = None) -> tuple[Engine, sessionmaker[Session]]:
    """Obtiene o inicializa el motor SQLAlchemy y la fábrica de sesiones: los de la base de esta
    ejecución (url_base_de_datos) o, si se pasa, los de esa ruta o URL."""
    url = url_base_de_datos() if ruta is None else _url_de(ruta)

    if url not in _motores:
        sqlite = not es_postgres(url)
        if sqlite and url.startswith("sqlite:///") and url != "sqlite:///:memory:":
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        motor = create_engine(url, **opciones_motor(url))
        if sqlite:
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


def _hay_predeterminadas(db: Session) -> bool:
    return bool(db.execute(
        select(func.count(CategoriaDB.id)).where(CategoriaDB.usuario_id.is_(None))
    ).scalar_one())


def _sembrar_predeterminadas(db: Session) -> None:
    """Inserta las 7 categorías predeterminadas (ids 1-7) si la tabla no tiene ninguna.

    Es la siembra básica del sistema: sin ellas la app no puede registrar movimientos. Solo se
    siembra si no hay ninguna predeterminada, así los reinicios de tests no duplican.

    Si dos instancias arrancan a la vez, las dos ven la tabla vacía e insertan: la segunda choca con
    la clave primaria. No es un error (la otra ya sembró), así que se deshace y se sigue."""
    if _hay_predeterminadas(db):
        return
    db.add_all([
        CategoriaDB(id=id_, nombre=nombre, tipo=tipo, usuario_id=None)
        for id_, nombre, tipo in PREDETERMINADAS
    ])
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return
    ajustar_secuencias(db)


def ajustar_secuencias(db: Session) -> None:
    """Deja la secuencia del id de cada tabla después de su mayor id. Solo hace falta en Postgres,
    donde insertar una fila con id fijo (las categorías predeterminadas) no avanza la secuencia: sin
    esto, la siguiente fila intentaría usar un id que ya existe. En SQLite no hace nada."""
    if db.get_bind().dialect.name != "postgresql":
        return
    from app.models import Base
    for tabla in Base.metadata.sorted_tables:
        if "id" in tabla.columns:
            db.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{tabla.name}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {tabla.name}), 0) + 1, false)"
            ))


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
    """Vacía todas las tablas, reinicia los contadores de ids y vuelve a sembrar las categorías
    predeterminadas. Para tests. Las tablas salen de los modelos (Base.metadata): una tabla nueva
    queda cubierta sin tocar esta función."""
    motor, fabrica = obtener_motor_y_sesion()
    from app.models import Base

    Base.metadata.create_all(bind=motor)
    tablas = [tabla.name for tabla in Base.metadata.sorted_tables]
    with fabrica() as db:
        if motor.dialect.name == "postgresql":
            db.execute(text(f"TRUNCATE {', '.join(tablas)} RESTART IDENTITY CASCADE"))
        else:
            # De las que dependen de otras hacia las demás, por las claves foráneas.
            for tabla in reversed(tablas):
                db.execute(text(f"DELETE FROM {tabla}"))
            for tabla in tablas:
                try:
                    db.execute(text(f"DELETE FROM sqlite_sequence WHERE name='{tabla}'"))
                except Exception:
                    # sqlite_sequence solo existe si ya hubo autoincrement
                    pass
        _sembrar_predeterminadas(db)
        db.commit()
