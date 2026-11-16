"""Fuente en móvil: Inter recortada, sin precarga y con un respaldo del mismo tamaño.

La precarga de inter-latin.woff2 competía con el CSS a 1,6 Mbps y retrasaba el primer pintado;
sin ella, lo que evita que el texto salte al llegar Inter es "Inter Fallback" (Arial ajustada).
"""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
STATIC = Path(__file__).resolve().parent.parent / "app/static"
ESTILOS = (STATIC / "css/styles.css").read_text()
TOKENS = (STATIC / "css/tokens.css").read_text()


def _caras(familia):
    """Bloques @font-face de una familia, como texto."""
    bloques = re.findall(r"@font-face\s*\{([^}]*)\}", ESTILOS)
    return [b for b in bloques if re.search(rf'font-family:\s*"{familia}";', b)]


def _puntos(bloque):
    """Puntos de código que cubre el unicode-range de un @font-face."""
    rango = re.search(r"unicode-range:\s*([^;]+);", bloque).group(1)
    puntos = set()
    for parte in rango.split(","):
        ini, _, fin = parte.strip().removeprefix("U+").partition("-")
        puntos.update(range(int(ini, 16), int(fin or ini, 16) + 1))
    return puntos


def test_ninguna_pagina_precarga_fuentes():
    for ruta in ("/login", "/resumen"):
        html = client.get(ruta).text
        assert not re.search(r'rel="preload"[^>]*as="font"', html), ruta
        assert "inter-latin.woff2" not in html, ruta


def test_inter_latin_recortada_sigue_siendo_woff2():
    fuente = (STATIC / "fonts/inter-latin.woff2").read_bytes()

    assert fuente[:4] == b"wOF2"
    # 47 KB la de Google; la recortada pesa 31 KB. Si vuelve a crecer, se perdió el recorte.
    assert len(fuente) < 36_000
    assert client.get("/static/fonts/inter-latin.woff2").status_code == 200


def test_respaldo_ajustado_para_los_tres_pesos():
    caras = _caras("Inter Fallback")
    pesos = sorted(int(re.search(r"font-weight:\s*(\d+);", c).group(1)) for c in caras)

    assert pesos == [400, 500, 600]
    for cara in caras:
        assert "local(" in cara and "url(" not in cara
        for descriptor in ("size-adjust", "ascent-override", "descent-override", "line-gap-override"):
            assert re.search(rf"{descriptor}:\s*[\d.]+%;", cara), descriptor


def test_respaldo_cubre_lo_mismo_que_inter():
    """Si el respaldo cubriera más, las flechas o los emojis dejarían de ir a la fuente del sistema."""
    inter = set().union(*(_puntos(c) for c in _caras("Inter")))

    for cara in _caras("Inter Fallback"):
        assert _puntos(cara) == inter
    assert ord("→") not in inter


def test_respaldo_va_justo_despues_de_inter():
    for variable in ("--font-display", "--font-text"):
        pila = re.search(rf"{variable}:\s*([^;]+);", TOKENS).group(1)
        assert pila.startswith('"Inter", "Inter Fallback", '), variable
