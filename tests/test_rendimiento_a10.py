"""Auditoría de rendimiento del 3 de noviembre, hallazgo A10 (detalles menores)."""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
JS = Path(__file__).resolve().parent.parent / "app" / "static" / "js"
SCRIPT_JS = '<script>document.documentElement.classList.add("js");</script>'


def _primer_css(html: str) -> int:
    return re.search(r'rel="stylesheet"|<style', html).start()


def test_script_en_linea_va_antes_de_las_hojas_de_estilos():
    # Un script en línea detrás de un <link rel="stylesheet"> espera a que cargue el CSS.
    for ruta in ("/resumen", "/movimientos", "/cuentas", "/categorias", "/presupuestos"):
        html = client.get(ruta).text
        assert html.count(SCRIPT_JS) == 1, ruta
        assert html.index(SCRIPT_JS) < _primer_css(html), ruta


def test_login_sigue_sin_la_clase_js():
    assert SCRIPT_JS not in client.get("/login").text


def test_desplegable_quita_los_listeners_globales_al_cerrar():
    codigo = (JS / "desplegable.js").read_text()
    # Ya no se ponen al cargar: se ponen al abrir y se quitan al cerrar.
    assert "document.addEventListener" not in codigo and "window.addEventListener" not in codigo
    assert "removeEventListener" in codigo
    for evento in ("desplegable:abierto", "desplegable:cerrado", '"keydown"', '"pointerdown"', '"pageshow"'):
        assert evento in codigo, evento


def test_analisis_precarga_solo_con_raton_o_foco_y_con_retardo():
    codigo = (JS / "analisis.js").read_text()
    assert '"pointerenter"' in codigo and 'event.pointerType === "mouse"' in codigo
    assert '"focus"' in codigo and '"blur"' in codigo and '"pointerleave"' in codigo
    assert re.search(r"RETARDO_PRECARGA = (\d+)", codigo).group(1) == "150"
