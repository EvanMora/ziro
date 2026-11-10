import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "app/static/css"


def test_capsulas_sin_backdrop_filter():
    # Detrás de las cápsulas solo está el gris liso del escenario: el filtro no se ve y
    # se recalculaba en cada frame de grow-y.
    estilos = (CSS / "resumen.css").read_text()
    reglas = re.findall(r"\.capsule(?:--\w+)?\s*\{([^}]*)\}", estilos)

    assert reglas
    for cuerpo in reglas:
        assert "backdrop-filter" not in cuerpo
