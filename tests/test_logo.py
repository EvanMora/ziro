"""Marca Ziro: nombre, logo (la Z de "Flujo") e íconos en todas las pantallas."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PAGINAS = ["/login", "/resumen", "/movimientos", "/cuentas", "/categorias"]

# Inicio de uno de los dos trazos de la Z, igual en el símbolo en línea y en los archivos.
TRAZO_DE_LA_Z = "M135.04 119.36"


@pytest.mark.parametrize("ruta", PAGINAS)
def test_cada_pantalla_usa_el_nombre_y_el_logo_de_ziro(ruta):
    html = client.get(ruta).text

    assert "Ziro</title>" in html
    assert "Mis Finanzas" not in html
    assert TRAZO_DE_LA_Z in html
    # El logo anterior (cuadrado con línea de tendencia) ya no aparece.
    assert "M5 13.5l3.5-3.5" not in html
    assert "M6 16l4.2-4.2" not in html


@pytest.mark.parametrize("ruta", PAGINAS)
def test_cada_pantalla_enlaza_los_iconos(ruta):
    html = client.get(ruta).text

    # url_for genera URLs absolutas (http://testserver/static/...), como en las hojas de estilo.
    assert '/static/img/favicon.svg" type="image/svg+xml">' in html
    assert '/static/img/favicon-32.png" type="image/png" sizes="32x32">' in html
    assert 'rel="apple-touch-icon" href="' in html
    assert '/static/img/apple-touch-icon.png">' in html


def test_los_iconos_se_sirven():
    svg = client.get("/static/img/favicon.svg")
    assert svg.status_code == 200
    assert TRAZO_DE_LA_Z in svg.text
    # En pestañas oscuras el cuadrado se aclara para no perderse.
    assert "prefers-color-scheme: dark" in svg.text

    for ruta, lado in (("/static/img/favicon-32.png", 32), ("/static/img/apple-touch-icon.png", 180)):
        png = client.get(ruta)
        assert png.status_code == 200, ruta
        assert png.content[:8] == b"\x89PNG\r\n\x1a\n", ruta
        ancho = int.from_bytes(png.content[16:20], "big")
        alto = int.from_bytes(png.content[20:24], "big")
        assert (ancho, alto) == (lado, lado), ruta


def test_la_tarjeta_del_login_dibuja_la_z_de_ziro():
    """Sobre el saludo va la Z animada: los dos trazos del símbolo (sale y entra), sin el logo viejo."""
    html = client.get("/login").text
    marca = html.split('class="login-card__mark"')[1].split("</span>")[0]

    assert 'viewBox="0 0 512 512"' in marca
    assert 'd="M135.04 148.48H289.6L166.4 271.68"' in marca  # lo que sale: baja
    assert 'd="M376.96 363.52H222.4L345.6 240.32"' in marca  # lo que entra: sube
    assert "M10 26l6.5-6.5" not in html
    assert "login-card__mark-dot" not in html


def test_el_logo_en_linea_hereda_el_color_del_texto():
    """El símbolo usa currentColor: se ve en el color del texto y la Z es un recorte transparente."""
    html = client.get("/resumen").text
    simbolo = html.split(TRAZO_DE_LA_Z)[0].rsplit("<svg", 1)[1]

    assert 'fill="currentColor"' in simbolo
    assert 'aria-hidden="true"' in simbolo
