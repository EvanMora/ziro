"""Los tests nunca tocan la base real (data/usuarios.sqlite): la base en memoria se elige antes de
importar la app, no en un fixture que corre después de que otro fixture ya vació las tablas."""
import os

from app.services import database


def test_los_tests_usan_una_base_en_memoria_desde_el_inicio():
    assert os.environ["DATABASE_PATH"] == "sqlite:///:memory:"
    assert "usuarios.sqlite" not in str(database.obtener_motor().url)
