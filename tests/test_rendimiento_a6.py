"""A6 de la auditoría de rendimiento: CSS que bloquea el pintado y que la página no usa.

El Resumen solo carga la barra del presupuesto (presupuesto-barra.css), no todo presupuestos.css,
y lo que solo usa el login vive en login.css, no en styles.css (que cargan todas las páginas)."""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
CSS = Path(__file__).resolve().parent.parent / "app/static/css"

# Clases que solo usa el login (login.html y login*.js).
SOLO_LOGIN = (".global-nav", ".wordmark", ".nav-cta", ".btn--shine", ".float-field__action",
              ".float-field__input--action", ".eye-slash", ".check-fancy")


def _hojas(html):
    return [h.rsplit("/", 1)[-1] for h in re.findall(r'rel="stylesheet" href="([^"]+\.css)"', html)]


def test_resumen_carga_solo_la_barra_del_presupuesto():
    hojas = _hojas(client.get("/resumen").text)

    assert "presupuesto-barra.css" in hojas
    assert "presupuestos.css" not in hojas


def test_presupuestos_carga_la_barra_antes_que_su_hoja():
    hojas = _hojas(client.get("/presupuestos").text)

    assert hojas.index("presupuesto-barra.css") < hojas.index("presupuestos.css")


def test_la_barra_del_presupuesto_no_esta_repetida():
    barra = (CSS / "presupuesto-barra.css").read_text()
    resto = (CSS / "presupuestos.css").read_text()

    for selector in (".pres-barra {", ".pres-pista {", ".pres-pista__relleno {", "@keyframes pista-in"):
        # Al inicio de línea: ".pres-barras .pres-pista {" es de Presupuestos y no cuenta.
        patron = r"(^|\n)" + re.escape(selector)
        assert re.search(patron, barra), selector
        assert not re.search(patron, resto), selector
    # La barra vacía en móvil y el movimiento reducido también son del Resumen.
    assert re.search(r"@media \(max-width: 640px\) \{\s*\.pres-barra--vacia", barra)
    assert re.search(r"@media \(prefers-reduced-motion: reduce\) \{\s*\.pres-pista__relleno", barra)


def test_lo_del_login_no_esta_en_styles_css():
    estilos = (CSS / "styles.css").read_text()
    login = (CSS / "login.css").read_text()

    for clase in SOLO_LOGIN:
        assert not re.search(re.escape(clase) + r"\b", estilos), clase
        assert re.search(re.escape(clase) + r"\b", login), clase


def test_login_carga_login_css_despues_de_styles_css():
    hojas = _hojas(client.get("/login").text)

    assert hojas.index("styles.css") < hojas.index("login.css")


def test_nav_cta_sin_animacion_con_movimiento_reducido():
    """Con la misma especificidad gana la última: el animation: none tiene que ir después de .nav-cta."""
    login = (CSS / "login.css").read_text()
    regla = login.index(".nav-cta {")
    reducido = re.search(r"@media \(prefers-reduced-motion: reduce\) \{\s*\.nav-cta \{\s*animation: none;", login)

    assert reducido and reducido.start() > regla
