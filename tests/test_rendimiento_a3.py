"""A3: contraer la barra lateral no anima el layout; lo anima una View Transition."""
import re

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_las_columnas_de_la_app_no_se_animan():
    css = client.get("/static/css/app.css").text

    assert not re.search(r"transition:[^;]*grid-template-columns", css)


def test_el_toggle_usa_view_transition_con_salida_directa():
    js = client.get("/static/js/app-shell.js").text
    css = client.get("/static/css/app.css").text

    assert "document.startViewTransition(" in js
    assert "!document.startViewTransition" in js
    assert "prefers-reduced-motion: reduce" in js
    # La clase que distingue esta transición de la del cambio de sección tiene sus reglas.
    assert 'classList.add("vt-barra")' in js and 'classList.remove("vt-barra")' in js
    assert ":root.vt-barra::view-transition-group(barra)" in css
