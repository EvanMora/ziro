"""Estructura de la app: barra lateral, secciones y pantalla de Resumen."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import movimientos
from app.web.formato import nombre_mes

client = TestClient(app)

SECCIONES = ["resumen", "movimientos", "cuentas", "categorias"]


@pytest.mark.parametrize("seccion", SECCIONES)
def test_cada_seccion_responde_y_marca_su_item(seccion):
    response = client.get(f"/{seccion}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert f'href="/{seccion}" title' in response.text
    assert response.text.count('aria-current="page"') == 1
    activo = response.text.split('aria-current="page"')[0].rsplit("<a", 1)[1]
    assert f'href="/{seccion}"' in activo


def test_barra_contraida_se_recuerda_con_cookie():
    abierta = TestClient(app).get("/resumen").text
    contraida_client = TestClient(app)
    contraida_client.cookies.set("barra_contraida", "1")
    contraida = contraida_client.get("/resumen").text

    assert 'class="shell" data-shell' in abierta
    assert 'class="shell is-collapsed" data-shell' in contraida
    assert 'aria-expanded="false"' in contraida


def test_resumen_muestra_las_cifras_del_contrato(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 11, 15))
    html = client.get("/resumen?anio=2026&mes=10").text

    assert "$4.382.900" in html
    assert "+$3.200.000" in html
    assert "−$1.874.300" in html
    assert "Te quedan <strong class=\"num\">$1.325.700</strong>" in html
    assert 'role="img"' in html and 'aria-label="Ingresos $3.200.000, gastos $1.874.300"' in html
    assert "Octubre 2026" in html


def test_resumen_muestra_la_deuda(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 11, 15))
    deuda = 'Debes <span class="num">$840.000</span> en tarjetas'
    assert deuda in client.get("/resumen?anio=2026&mes=10").text

    r = client.post("/api/v1/cuentas/4/pagos", json={"monto": "840000", "cuenta_origen_id": 1, "fecha": "2026-11-12"})
    assert r.status_code == 201
    html = client.get("/resumen?anio=2026&mes=10").text
    assert deuda not in html
    assert "En 3 cuentas · Ver cuentas" in html


def test_selector_de_mes():
    html = client.get("/resumen?anio=2026&mes=1").text

    assert 'href="/resumen?anio=2025&amp;mes=12"' in html
    assert 'href="/resumen?anio=2026&amp;mes=2"' in html


def test_no_deja_ir_a_meses_futuros():
    hoy = date.today()
    html = client.get(f"/resumen?anio={hoy.year + 1}&mes=1").text

    assert f"{nombre_mes(hoy.month).capitalize()} {hoy.year}" in html
    assert "month__off" in html  # la flecha "siguiente" está desactivada en el mes actual


def test_mes_invalido_muestra_el_mes_actual():
    """Una URL mal escrita muestra la página con el mes actual, no un error en JSON."""
    hoy = date.today()
    r = client.get("/resumen?anio=2026&mes=13")

    assert r.status_code == 200
    assert f"{nombre_mes(hoy.month).capitalize()} {hoy.year}" in r.text


def test_login_redirige_al_resumen():
    assert 'data-redirect="/resumen"' in client.get("/login").text


def test_archivos_de_la_app():
    for path in ("/static/css/app.css", "/static/css/resumen.css", "/static/css/movimientos.css",
                 "/static/js/app-shell.js"):
        assert client.get(path).status_code == 200, path


@pytest.mark.parametrize("seccion", SECCIONES)
def test_dialogo_en_todas_las_secciones(seccion):
    html = client.get(f"/{seccion}").text

    assert 'id="dialogo-movimiento"' in html
    dialogo = html.split('id="dialogo-movimiento"', 1)[1].split("</dialog>", 1)[0]
    assert dialogo.count('data-tipo="gasto"') == 5 and dialogo.count('data-tipo="ingreso"') == 2
    assert f'max="{date.today().isoformat()}"' in html
    assert 'maxlength="80"' in html
    assert 'data-toast' in html


def test_boton_nuevo_movimiento():
    html = client.get("/resumen").text

    assert 'href="/movimientos?nuevo=1"' in html
    assert "data-nuevo-movimiento" in html


def test_scripts_del_dialogo():
    html = client.get("/resumen").text

    assert "js/movimiento-dialogo.js" in html
    assert "js/movimientos.js" not in html  # solo en Movimientos
    assert "js/movimientos.js" in client.get("/movimientos").text
    for path in ("/static/js/movimiento-dialogo.js", "/static/js/movimientos.js"):
        assert client.get(path).status_code == 200, path


def test_la_navegacion_de_meses_usa_la_fecha_de_la_app(monkeypatch):
    """El selector de mes y el tope de meses futuros usan movimientos.hoy(), como el resto de la
    app, no la fecha del sistema (así las pruebas con fecha fija no dependen del mes real)."""
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2027, 3, 10))

    html = client.get("/resumen?anio=2030&mes=1").text

    assert "Marzo 2027" in html
    assert "month__off" in html  # no hay mes siguiente
    assert 'href="/resumen?anio=2027&amp;mes=2"' in html
