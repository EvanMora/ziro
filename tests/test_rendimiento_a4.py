"""Regresión A4: la animación de entrada no debe esconder el contenido ni alargarse."""

import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "app" / "static" / "css"


def _bloque(texto: str, cabecera: str) -> str:
    inicio = texto.index(cabecera)
    return texto[inicio : texto.index("\n}", inicio)]


def test_view_in_no_anima_la_opacidad():
    # Con opacidad 0 el contenido no se ve y Chrome lo descarta como LCP.
    assert "opacity" not in _bloque((CSS / "app.css").read_text(), "@keyframes view-in")


def test_barras_crecen_sin_espera_y_en_400ms_o_menos():
    resumen = (CSS / "resumen.css").read_text()
    for nombre in ("grow-y", "grow-x"):
        declaracion = re.search(rf"animation: {nombre} (\d+)ms [^;]*;", resumen)
        assert declaracion, nombre
        assert int(declaracion.group(1)) <= 400
        # Un segundo tiempo en la declaración sería un retraso.
        assert len(re.findall(r"\d+ms", declaracion.group(0))) == 1

    relleno = _bloque((CSS / "presupuesto-barra.css").read_text(), ".pres-pista__relleno {")
    assert "pista-in 400ms" in relleno
    assert "200ms" not in relleno


# El cambio de sección ya no es un fundido en serie sino un deslizamiento sin opacidad:
# lo comprueba test_desplazamiento_secciones.py (test_la_vieja_y_la_nueva_van_pegadas).
