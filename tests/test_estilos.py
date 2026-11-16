"""Reglas de CSS que, si se pierden, rompen pantallas sin que ninguna otra prueba lo note."""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "app/static/css"


def test_hidden_siempre_oculta():
    """Los diálogos ocultan partes con el atributo hidden. Sin esta regla, cualquier clase que ponga
    display (como .field) lo anula y la parte se ve igual: pasó con "Pasar sus movimientos a"."""
    estilos = (CSS / "styles.css").read_text()

    assert re.search(r"(^|\n)\[hidden\]\s*\{\s*display:\s*none\s*!important;?\s*\}", estilos)
