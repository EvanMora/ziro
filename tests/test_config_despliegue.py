"""Configuración para desplegar (docs/superpowers/specs/2026-11-16-vercel-design.md): de dónde sale la
base de datos, qué cuenta como producción y qué exige la app para arrancar ahí. Ningún test de este
archivo se conecta a una base distinta de la de los tests."""
from pathlib import Path

import pytest

from app import config, main
from app.services import database

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
