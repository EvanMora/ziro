"""Página de Categorías: gastos e ingresos del mes, enlace a sus movimientos y lápiz solo en las propias."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.categorias import CategoriaEntrada
from app.services import categorias, movimientos

client = TestClient(app)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 11, 1))


def test_gastos_e_ingresos_del_mes():
    html = client.get("/categorias?anio=2026&mes=10").text

    assert "Categorías · " in html
    assert 'id="grupo-gasto">Gastos' in html and 'id="grupo-ingreso">Ingresos' in html
    assert "Octubre · <span class=\"num\">$1.874.300</span>" in html
    assert "−$1.100.000" in html and "+$3.200.000" in html
    assert "2 movimientos · 20,5\u00a0%" in html  # Mercado: 384.300 de 1.874.300
    assert "Sin movimientos" in html  # Otros gastos
    assert html.index(">Arriendo<") < html.index(">Mercado<") < html.index(">Otros gastos<")
    assert 'href="/movimientos?anio=2026&amp;mes=10&amp;categoria=3"' in html
    assert 'href="/categorias?anio=2026&amp;mes=9"' in html  # selector de mes


def test_solo_las_propias_tienen_lapiz():
    html = client.get("/categorias?anio=2026&mes=10").text
    assert "data-editar-categoria" not in html

    creada = categorias.crear(1, CategoriaEntrada(nombre="Mascotas", tipo="gasto"))
    html = client.get("/categorias?anio=2026&mes=10").text

    assert html.count("data-editar-categoria") == 1
    assert 'aria-label="Editar Mascotas"' in html
    assert f'data-categoria=\'{{"id": {creada.id}, "nombre": "Mascotas", "tipo": "gasto", "usos": 0}}\'' in html


def test_la_categoria_nueva_aparece_en_los_diálogos():
    categorias.crear(1, CategoriaEntrada(nombre="Mascotas", tipo="gasto"))

    html = client.get("/movimientos?anio=2026&mes=10").text

    assert 'data-tipo="gasto">Mascotas</option>' in html


def test_nombre_con_html_se_escapa():
    categorias.crear(1, CategoriaEntrada(nombre="<b>x</b>'", tipo="gasto"))

    html = client.get("/categorias?anio=2026&mes=10").text

    assert "<b>x</b>" not in html


def test_mes_futuro_muestra_el_actual():
    html = client.get("/categorias?anio=2030&mes=1").text

    assert "Noviembre · " in html


@pytest.mark.parametrize("guardado", ["%C2%B2", "9" * 5000, "abc"])
def test_guardado_invalido_no_rompe(guardado):
    r = client.get(f"/categorias?anio=2026&mes=10&guardado={guardado}")

    assert r.status_code == 200
    assert "data-guardado" not in r.text


def test_guardado_valido_se_marca():
    assert 'data-guardado="3"' in client.get("/categorias?anio=2026&mes=10&guardado=3").text
