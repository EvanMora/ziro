"""Qué base usan los tests. No importa nada de la app: tests/conftest.py lo usa antes de cargarla."""
from collections.abc import Mapping
from urllib.parse import urlsplit

EN_MEMORIA = "sqlite:///:memory:"
VARIABLE = "ZIRO_TEST_DATABASE_URL"


def url_de_tests(entorno: Mapping[str, str]) -> str:
    """SQLite en memoria, salvo que ZIRO_TEST_DATABASE_URL pida correr la suite contra un Postgres.

    Cada test vacía TODAS las tablas de esa base. Por eso solo se acepta un Postgres cuyo nombre de
    base contenga "test" o "prueba": pegar aquí por error la URL de producción borraría los datos
    de todos."""
    url = entorno.get(VARIABLE)
    if not url:
        return EN_MEMORIA
    partes = urlsplit(url)
    base = partes.path.lstrip("/").lower()
    if not partes.scheme.startswith("postgres") or not ("test" in base or "prueba" in base):
        raise RuntimeError(
            f"{VARIABLE} no parece una base de pruebas: los tests vacían todas las tablas, así que solo "
            'se acepta un Postgres cuyo nombre de base contenga "test" o "prueba" (p. ej. .../ziro_test).'
        )
    return url
