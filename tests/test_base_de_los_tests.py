"""Los tests nunca tocan la base real (data/usuarios.sqlite): la base de los tests (en memoria, o la de
ZIRO_TEST_DATABASE_URL) se elige antes de importar la app, no en un fixture que corre después de que
otro fixture ya vació las tablas."""
import os

from app.services import database


def test_los_tests_usan_su_propia_base_desde_el_inicio():
    esperada = os.environ.get("ZIRO_TEST_DATABASE_URL", "sqlite:///:memory:")

    assert os.environ["DATABASE_PATH"] == esperada
    assert os.environ["DATABASE_URL"] == esperada
    assert database.url_base_de_datos() == database.normalizar_url(esperada)
    assert "usuarios.sqlite" not in str(database.obtener_motor().url)
