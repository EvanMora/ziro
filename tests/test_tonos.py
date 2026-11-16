"""Tonos de los íconos de cuentas (la única excepción de color del sistema de diseño): el trazo se
lee sobre su fondo y no se confunde con los colores de ingreso, alerta ni error."""
import re
from pathlib import Path

import pytest

TOKENS = (Path(__file__).resolve().parent.parent / "app/static/css/tokens.css").read_text()
TONOS = ["azul", "indigo", "violeta", "ciruela", "petroleo", "cafe", "arena", "grafito"]


def color(nombre: str) -> tuple[int, int, int]:
    valor = re.search(rf"--{nombre}:\s*#([0-9a-fA-F]{{6}})\s*;", TOKENS).group(1)
    return tuple(int(valor[i:i + 2], 16) for i in (0, 2, 4))


def luminancia(rgb) -> float:
    def canal(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a, b) -> float:
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@pytest.mark.parametrize("tono", TONOS)
def test_contraste_de_los_tonos(tono):
    assert contraste(color(f"tono-{tono}"), color(f"tono-{tono}-bg")) >= 4.5


@pytest.mark.parametrize("tono", TONOS)
@pytest.mark.parametrize("estado", ["color-income", "color-warning", "color-danger"])
def test_los_tonos_no_parecen_colores_de_estado(tono, estado):
    a, b = color(f"tono-{tono}"), color(estado)
    assert sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5 >= 60
