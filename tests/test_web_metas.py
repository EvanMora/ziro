"""Página de Metas: estado vacío, tarjetas con progreso y textos por estado, y el menú."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.metas import AporteEntrada, MetaEntrada
from app.services import metas, movimientos
from tests.plantilla import USUARIO_PRUEBA_ID as U

client = TestClient(app)
HOY = date(2026, 11, 16)


@pytest.fixture(autouse=True)
def _hoy(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: HOY)


def _meta(nombre="Viaje", objetivo="2000000", fecha=date(2026, 12, 31), aporte=None):
    m = metas.crear(U, MetaEntrada(nombre=nombre, objetivo=Decimal(objetivo), fecha_limite=fecha))
    if aporte:
        metas.aportar(U, m.id, AporteEntrada(monto=Decimal(aporte), fecha=HOY))
    return m


def test_metas_esta_en_el_menu_y_no_en_proximamente():
    html = client.get("/resumen").text

    assert 'href="/metas"' in html
    assert "Próximamente" not in html
    assert "Fase 2" not in html


def test_estado_vacio():
    html = client.get("/metas").text

    assert "Todavía no tienes metas" in html
    assert "data-nueva-meta" in html
    assert 'id="dialogo-meta"' in html and 'id="dialogo-aporte"' in html


def test_tarjeta_de_una_meta_al_dia():
    _meta(aporte="500000")
    html = client.get("/metas").text

    assert "Viaje" in html
    assert "$500.000" in html and "$2.000.000" in html
    assert "Vas al día" in html
    assert "Te faltan $1.500.000" in html
    assert "Guarda $750.000 al mes hasta el 31 dic" in html
    assert "data-aportar" in html and "data-retirar" in html
    assert 'aria-label="Progreso: 25,0\u00a0%"' in html


def test_textos_por_estado(monkeypatch):
    _meta("Sin fecha", fecha=None)
    _meta("Lista", objetivo="1000", aporte="1000")
    _meta("Este mes", fecha=date(2026, 11, 30))
    _meta("Lejos", fecha=date(2027, 3, 1))
    html = client.get("/metas").text

    assert "¡Cumplida!" in html
    assert "Sin fecha" in html
    assert "Guarda $2.000.000 este mes" in html
    assert "hasta el 1 mar 2027" in html  # otro año: con el año


def test_vencida(monkeypatch):
    _meta(fecha=date(2026, 11, 20))
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 12, 2))

    html = client.get("/metas").text
    assert "Venció el 20 nov" in html


def test_sin_ahorro_no_se_puede_retirar():
    _meta()
    html = client.get("/metas").text

    assert "data-retirar" in html and "disabled" in html.split("data-retirar", 1)[1].split(">", 1)[0]


def test_ultimos_aportes_con_borrar():
    m = _meta(aporte="100000")
    metas.aportar(U, m.id, AporteEntrada(monto=Decimal(20000), fecha=HOY, retiro=True))
    html = client.get("/metas").text

    assert "+$100.000" in html and "−$20.000" in html
    assert html.count("data-borrar-aporte") == 2


def test_totales():
    _meta("Uno", objetivo="1000", aporte="500")
    _meta("Dos", objetivo="3000", aporte="250")
    html = client.get("/metas").text

    assert "$750" in html and "$4.000" in html


def test_estaticos():
    for ruta in ("/static/js/metas.js", "/static/css/metas.css"):
        assert client.get(ruta).status_code == 200
