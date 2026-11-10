"""Cambio de sección tipo feed: la sección vieja sale entera hacia arriba y la nueva entra desde
abajo (al revés si la sección de destino está más arriba en el menú). Sin fundido: con él quedaba
un instante vacío entre las dos, que se veía como un parpadeo."""
import re

from fastapi.testclient import TestClient

from app.main import app
from app.web.views import SECCIONES

client = TestClient(app)


def _head(ruta: str) -> str:
    html = client.get(ruta).text
    return html[: html.index("</head>")]


def _css(nombre: str) -> str:
    return client.get(f"/static/css/{nombre}").text


def _bloque(texto: str, cabecera: str) -> str:
    inicio = texto.index(cabecera)
    return texto[inicio : texto.index("\n}", inicio)]


# ---------- Dirección (script en línea del <head>) ----------

def test_el_head_conoce_el_orden_de_las_secciones():
    orden = ", ".join(f'"{ruta}"' for ruta, _, _ in SECCIONES)
    for ruta in ("/resumen", "/movimientos", "/presupuestos"):
        assert f"[{orden}]" in _head(ruta), ruta


def test_pagereveal_marca_la_direccion_con_tipos_de_transicion():
    # Va en pagereveal (en línea, antes del primer pintado) para que el CSS la vea desde el inicio.
    head = _head("/resumen")
    assert 'destino > origen ? "hacia-abajo" : "hacia-arriba"' in head
    reveal = head[head.index('addEventListener("pagereveal"') :]
    assert "e.viewTransition.types.add(tipo)" in reveal


def test_sin_direccion_no_hay_animacion():
    # Misma sección (p. ej. /presupuestos -> /presupuestos/nuevo, o recargar tras guardar) o una
    # página fuera del menú: cambia al instante, sin deslizar hacia ningún lado.
    head = _head("/resumen")
    assert "origen < 0 || destino < 0 || origen === destino" in head


def test_al_llegar_deslizando_se_marca_la_pagina():
    # La clase se queda toda la vida de la página: si se quitara al terminar la transición, las
    # animaciones de entrada que apaga arrancarían en ese momento.
    head = _head("/resumen")
    assert 'classList.add("vt-seccion")' in head


def test_al_salir_se_cierra_el_cajon_del_celular_antes_de_la_captura():
    head = _head("/resumen")
    assert 'classList.add("vt-cierra-cajon")' in head
    assert 'classList.remove("is-open")' in head
    assert ".vt-cierra-cajon .scrim" in _css("app.css")


# ---------- Animación (app.css) ----------

def test_la_barra_superior_se_queda_quieta_y_el_contenido_se_desliza_debajo():
    css = _css("app.css")
    assert re.search(r"\.topbar \{\s*view-transition-name: barra-superior;", css)
    # .main ya no se captura entero en el cambio de sección (solo al contraer la barra lateral).
    assert not re.search(r"^\.main \{\s*view-transition-name", css, re.M)
    assert ".vt-barra .main" in css


def test_el_contenido_se_desliza_sin_fundido():
    css = _css("app.css")
    for tipo in ("hacia-abajo", "hacia-arriba"):
        for lado in ("old", "new"):
            regla = _bloque(css, f":root:active-view-transition-type({tipo})::view-transition-{lado}(root) {{")
            assert "animation-name: vt-" in regla, (tipo, lado)
    for nombre in ("vt-sale-arriba", "vt-entra-abajo", "vt-sale-abajo", "vt-entra-arriba"):
        cuadros = _bloque(css, f"@keyframes {nombre} {{")
        assert "translateY" in cuadros, nombre
        # Solo transform: lo mueve la GPU sin repintar, y sin opacidad no hay instante vacío.
        assert "opacity" not in cuadros, nombre


def test_la_vieja_y_la_nueva_van_pegadas():
    # Misma duración y curva: si una fuera más rápida se abriría un hueco o se montarían.
    css = _css("app.css")
    regla = _bloque(css, ":root:active-view-transition-type(hacia-abajo, hacia-arriba)::view-transition-image-pair(root) {")
    assert "isolation: auto" in regla
    tiempos = _bloque(css, ":root:active-view-transition-type(hacia-abajo, hacia-arriba)::view-transition-old(root),")
    assert "animation-duration: 420ms" in tiempos
    assert "animation-timing-function: var(--ease-emphasized)" in tiempos
    assert "mix-blend-mode: normal" in tiempos


def test_ya_no_queda_el_fundido_viejo():
    css = _css("app.css")
    assert "vt-fuera" not in css and "vt-dentro" not in css


# ---------- Nada más se anima mientras se desliza ----------

def test_las_entradas_de_las_secciones_se_apagan_al_llegar_deslizando():
    assert re.search(r"\.vt-seccion \.view > \*[^{]*\{\s*animation: none;", _css("app.css"))
    assert re.search(r"\.vt-seccion \.capsule,\s*\.vt-seccion \.cats__bar \{\s*animation: none;", _css("resumen.css"))
    assert re.search(r"\.vt-seccion \.pres-pista__relleno \{\s*animation: none;", _css("presupuesto-barra.css"))


def test_la_pildora_no_tapa_el_texto_de_la_seccion_mientras_se_desliza():
    # La píldora es una captura aparte encima de la barra lateral: pintada normal, su gris tapaba
    # el nombre de la sección. Multiplicada, el texto de debajo se ve a través de ella.
    regla = _bloque(_css("app.css"), "::view-transition-group(indicador) {")
    assert "mix-blend-mode: multiply" in regla
