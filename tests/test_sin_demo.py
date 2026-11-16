"""La app no siembra datos de demostración: una cuenta nueva empieza solo con las 7 categorías
predeterminadas (spec 2026-11-16-crear-cuenta-design.md, sección 6). La plantilla de datos vive en
tests/plantilla.py y solo la usan los tests."""
import subprocess
from pathlib import Path

import pytest

from app.services import categorias, cuentas, movimientos, presupuestos, usuarios

pytestmark = pytest.mark.sin_plantilla

APP = Path(__file__).resolve().parent.parent / "app"


@pytest.fixture
def usuario_id():
    # El primer usuario de la base recibe el id 1: el que antes heredaba el demo.
    nuevo = usuarios.crear("ana@x.com", "secreta123", "Ana")
    assert nuevo.id == 1
    return nuevo.id


def test_usuario_nuevo_no_tiene_cuentas(usuario_id):
    assert cuentas.listar(usuario_id) == []


def test_usuario_nuevo_no_tiene_movimientos(usuario_id):
    hoy = movimientos.hoy()
    assert movimientos.listar(usuario_id, hoy.year, hoy.month).movimientos == []
    assert movimientos.listar(usuario_id, 2026, 10).movimientos == []


def test_usuario_nuevo_no_tiene_presupuesto(usuario_id):
    anio, mes = presupuestos._mes_anterior(movimientos.hoy())
    assert presupuestos.del_mes(usuario_id, anio, mes).creado is False


def test_usuario_nuevo_tiene_las_categorias_predeterminadas(usuario_id):
    lista = categorias.listar(usuario_id)
    assert len(lista) == 7
    assert all(c.predeterminada for c in lista)


def test_la_app_no_habla_de_demo():
    r = subprocess.run(["grep", "-rnE", "DEMO_USUARIO_ID|USUARIO_DEMO|_sembrar_demo|ref_plantilla|_EJEMPLO", str(APP)],
                       capture_output=True, text=True)
    assert r.stdout == ""
