"""Configuración para desplegar (docs/superpowers/specs/2026-11-16-vercel-design.md): de dónde sale la
base de datos, qué cuenta como producción y qué exige la app para arrancar ahí. Ningún test de este
archivo se conecta a una base distinta de la de los tests."""
import inspect
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

from app import config, main
from app.models import Base
from app.schemas.categorias import CategoriaEntrada
from app.schemas.metas import MetaEntrada
from app.services import categorias, database, metas, usuarios

RAIZ = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.sin_plantilla


@pytest.fixture
def entorno_limpio():
    """Sin ninguna de las variables que deciden el modo ni la base. Usa su propio MonkeyPatch para
    restaurar el entorno apenas termina el test: los fixtures de conftest.py vacían la base al final
    y, con el entorno aún en modo producción y sin DATABASE_URL, fallarían."""
    with pytest.MonkeyPatch.context() as entorno:
        for variable in ("ENVIRONMENT", "VERCEL", "DATABASE_URL"):
            entorno.delenv(variable, raising=False)
        yield entorno


# ---------- URL de la base ----------

NEON = "ep-x-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"


@pytest.mark.parametrize(("url", "esperada"), [
    ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    (f"postgresql://u:p@{NEON}", f"postgresql+psycopg://u:p@{NEON}"),
    ("postgresql+psycopg://u@h/db", "postgresql+psycopg://u@h/db"),
    ("sqlite:///data/x.sqlite", "sqlite:///data/x.sqlite"),
])
def test_normalizar_url_postgres(url, esperada):
    assert database.normalizar_url(url) == esperada


def test_database_url_tiene_prioridad(entorno_limpio):
    entorno_limpio.setenv("DATABASE_URL", "postgres://u:p@h/db")
    entorno_limpio.setattr(database, "DATABASE_PATH", "data/otra.sqlite")

    assert database.url_base_de_datos() == "postgresql+psycopg://u:p@h/db"


def test_sin_database_url_usa_database_path(entorno_limpio):
    entorno_limpio.setattr(database, "DATABASE_PATH", "data/x.sqlite")

    assert database.url_base_de_datos() == "sqlite:///data/x.sqlite"


def test_database_url_vacia_no_cuenta(entorno_limpio):
    entorno_limpio.setenv("DATABASE_URL", "")
    entorno_limpio.setattr(database, "DATABASE_PATH", "sqlite:///:memory:")

    assert database.url_base_de_datos() == "sqlite:///:memory:"


@pytest.mark.parametrize("variables", [{"ENVIRONMENT": "production"}, {"VERCEL": "1"}])
def test_produccion_sin_database_url_falla(entorno_limpio, variables):
    for nombre, valor in variables.items():
        entorno_limpio.setenv(nombre, valor)

    with pytest.raises(RuntimeError, match="DATABASE_URL es obligatoria"):
        database.url_base_de_datos()


def test_es_postgres():
    assert database.es_postgres("postgresql+psycopg://u@h/db")
    assert not database.es_postgres("sqlite:///:memory:")


# ---------- Producción ----------

def test_es_produccion(entorno_limpio):
    assert config.es_produccion() is False
    assert config.en_vercel() is False

    entorno_limpio.setenv("ENVIRONMENT", "production")
    assert config.es_produccion() is True
    assert config.en_vercel() is False

    entorno_limpio.delenv("ENVIRONMENT")
    entorno_limpio.setenv("VERCEL", "1")
    assert config.es_produccion() is True
    assert config.en_vercel() is True


def test_vista_previa_de_vercel_exige_secret_key(entorno_limpio):
    # En una vista previa Vercel pone VERCEL pero nadie puso ENVIRONMENT: con una clave al azar,
    # cada instancia firmaría las cookies con una distinta y cerraría sesiones al azar.
    entorno_limpio.setenv("VERCEL", "1")
    entorno_limpio.delenv("SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        main.clave_secreta()


# ---------- Dependencias ----------

def test_requirements_de_produccion():
    produccion = (RAIZ / "requirements.txt").read_text(encoding="utf-8")
    desarrollo = (RAIZ / "requirements-dev.txt").read_text(encoding="utf-8")

    assert "psycopg[binary]==" in produccion
    assert "pytest" not in produccion
    assert "-r requirements.txt" in desarrollo
    assert "pytest==" in desarrollo


# ---------- Postgres: secuencias, siembra concurrente y reiniciar ----------

def _categorias_predeterminadas() -> int:
    with database.sesion() as db:
        return db.execute(text("SELECT COUNT(*) FROM categorias WHERE usuario_id IS NULL")).scalar_one()


def test_siembra_tolera_otra_instancia(monkeypatch):
    # Dos instancias arrancan a la vez: las dos ven la tabla vacía e insertan los ids 1-7. La
    # segunda choca con la clave primaria; no es un error, la otra ya sembró.
    assert _categorias_predeterminadas() == 7
    monkeypatch.setattr(database, "_hay_predeterminadas", lambda db: False)

    with database.sesion() as db:
        database._sembrar_predeterminadas(db)

    assert _categorias_predeterminadas() == 7


def test_reiniciar_no_tiene_lista_de_tablas():
    # Una tabla nueva (p. ej. transferencias) no obliga a tocar reiniciar(): sale de los modelos.
    assert "pagos_tarjeta" not in inspect.getsource(database.reiniciar)
    usuario = usuarios.crear("ana@x.com", "secreta123", "Ana")
    metas.crear(usuario.id, MetaEntrada(nombre="Viaje", objetivo=Decimal(1000), fecha_limite=None))

    database.reiniciar()

    with database.sesion() as db:
        filas = {tabla.name: db.execute(text(f"SELECT COUNT(*) FROM {tabla.name}")).scalar_one()
                 for tabla in Base.metadata.sorted_tables}
    assert filas.pop("categorias") == 7
    assert set(filas.values()) == {0}, filas


def test_ajustar_secuencias_no_falla():
    # En SQLite no hace nada; en Postgres deja cada secuencia después del mayor id.
    with database.sesion() as db:
        database.ajustar_secuencias(db)


def test_despues_de_sembrar_los_ids_siguen_sin_chocar():
    # Las predeterminadas se insertan con ids fijos (1-7). En Postgres eso no avanza la secuencia:
    # sin ajustarla, la primera categoría propia intentaría usar el id 1.
    usuario = usuarios.crear("ana@x.com", "secreta123", "Ana")

    propia = categorias.crear(usuario.id, CategoriaEntrada(nombre="Mascotas", tipo="gasto"))

    assert propia.id == 8
