"""Los tests nunca tocan una base real. La base de los tests (en memoria, o la de
ZIRO_TEST_DATABASE_URL) se elige antes de importar la app, no en un fixture que corre después de que
otro fixture ya vació las tablas. Y como cada test vacía todas las tablas, una base Postgres solo se
acepta si su nombre dice que es de pruebas."""
import os

import pytest

from app.services import database
from tests.base_de_pruebas import url_de_tests


def test_los_tests_usan_su_propia_base_desde_el_inicio():
    esperada = url_de_tests(os.environ)

    assert os.environ["DATABASE_PATH"] == esperada
    assert os.environ["DATABASE_URL"] == esperada
    assert database.url_base_de_datos() == database.normalizar_url(esperada)
    assert "usuarios.sqlite" not in str(database.obtener_motor().url)


def test_sin_variable_la_base_es_en_memoria():
    assert url_de_tests({}) == "sqlite:///:memory:"


@pytest.mark.parametrize("url", [
    "postgresql+psycopg://postgres:ziro@localhost:55432/ziro_test",
    "postgresql://u:p@ep-x.us-east-1.aws.neon.tech/ziro_pruebas?sslmode=require",
    "postgres://u:p@h/TEST_ziro",
])
def test_acepta_una_base_que_se_llama_de_pruebas(url):
    assert url_de_tests({"ZIRO_TEST_DATABASE_URL": url}) == url


@pytest.mark.parametrize("url", [
    "postgresql://u:p@ep-x.us-east-1.aws.neon.tech/neondb?sslmode=require",  # la de producción de Neon
    "postgresql://test:test@test-host/ziro",  # "test" en el usuario o el host no cuenta
    "postgres://u:p@h/",
    "sqlite:///data/usuarios.sqlite",
    "data/usuarios.sqlite",
])
def test_rechaza_una_base_que_no_es_de_pruebas(url):
    with pytest.raises(RuntimeError, match="vacían todas las tablas"):
        url_de_tests({"ZIRO_TEST_DATABASE_URL": url})
