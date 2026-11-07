"""Rendimiento del diálogo "Nuevo movimiento" (auditoría del 3 de noviembre, hallazgo A7).

- El aviso tras guardar viaja en la URL (?aviso=<clave>) y lo muestra app-shell.js: nadie lee
  sessionStorage en cada carga.
- Cada clave que se envía existe en el catálogo de app-shell.js (si no, el aviso no saldría).
- La flecha de los select del diálogo es un <svg> en el HTML, no la imagen data-URI de .select.
- El monto tiene autofocus: showModal() lo enfoca directo, sin pasar por el botón de cerrar.
"""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
JS = Path(__file__).resolve().parent.parent / "app" / "static" / "js"
ESCRIBEN_AVISO = ("movimiento-dialogo.js", "cuentas.js", "categorias.js", "pago-dialogo.js", "presupuesto-nuevo.js",
                  "ordenar-otros.js")


def _avisos_de_app_shell():
    shell = (JS / "app-shell.js").read_text()
    catalogo = shell.split("const AVISOS = {", 1)[1].split("};", 1)[0]
    return dict(re.findall(r'"([a-z-]+)": "([^"]+)"', catalogo))


def test_nadie_usa_sessionstorage_para_el_aviso():
    for nombre in ESCRIBEN_AVISO:
        js = (JS / nombre).read_text()
        assert "sessionStorage" not in js, nombre
        assert 'searchParams.set("aviso"' in js, nombre


def test_las_claves_de_aviso_existen_en_app_shell():
    avisos = _avisos_de_app_shell()
    usadas = set()
    for nombre in ESCRIBEN_AVISO:
        js = (JS / nombre).read_text()
        # irDespues("clave", ...), irDespues(x ? "clave" : "clave") y las del presupuesto.
        for llamada in re.findall(r"irDespues\(([^;]*?)\)", js) + re.findall(r'"aviso", ([^;]*?)\);', js):
            usadas |= set(re.findall(r'"([a-z]+-[a-z-]+)"', llamada))
    assert len(usadas) == 12
    assert usadas <= avisos.keys(), usadas - avisos.keys()


def test_el_dialogo_no_lee_el_aviso_al_cargar():
    js = (JS / "movimiento-dialogo.js").read_text()
    assert "data-toast" not in js
    assert "window.dialogoMovimiento = {" in js
    for metodo in ("abrir", "interpretar", "abrirConSugerencia"):
        assert f"{metodo}: (" in js, metodo


def test_flecha_svg_en_los_select_del_dialogo():
    html = client.get("/resumen").text
    dialogo = html.split('id="dialogo-movimiento"', 1)[1].split("</dialog>", 1)[0]

    for campo in ("mov-categoria", "mov-cuenta"):
        bloque = dialogo.split('<div class="select-flecha">', 2)[1 if campo == "mov-categoria" else 2]
        assert f'id="{campo}"' in bloque.split("</select>", 1)[0]
        assert bloque.split("</select>", 1)[1].lstrip().startswith('<svg viewBox="0 0 12 12" aria-hidden="true">')

    css = client.get("/static/css/app.css").text
    assert re.search(r"\.select-flecha > \.select \{\s*background-image: none;", css)


def test_monto_con_autofocus():
    html = client.get("/resumen").text
    monto = re.search(r'<input[^>]*id="mov-monto"[^>]*>', html).group(0)
    assert "autofocus" in monto
