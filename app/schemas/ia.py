"""Contratos del asistente con Gemini.

- Movimientos: el usuario escribe algo como "ayer gasté 45.000 en taxi con efectivo"; Gemini lo
  interpreta y la API devuelve un MovimientoSugerido. Es solo una sugerencia: el diálogo la muestra
  en el formulario y el usuario la revisa y guarda como siempre (POST /api/v1/movimientos).
- Resumen: AnalisisMes, observaciones y un consejo sobre las cifras del mes.
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.movimientos import Tipo

MAX_TEXTO = 300


class InterpretarEntrada(BaseModel):
    texto: str


class MovimientoSugerido(BaseModel):
    """Lo que se pudo entender. Cada campo que no se entendió (o no es válido) llega en null y el
    diálogo lo deja como estaba."""
    tipo: Tipo
    monto: Decimal | None = None
    categoria_id: int | None = None
    cuenta_id: int | None = None
    fecha: date | None = None
    descripcion: str = ""
    # Nombre de una categoría nueva que el diálogo ofrece ya elegida y crea solo si se guarda. Viene
    # cuando ninguna categoría encaja (categoria_id es entonces la de "Otros" de ese tipo).
    categoria_nueva: str | None = None


class AnalisisMes(BaseModel):
    """Análisis del Resumen. Texto plano (la plantilla lo muestra como texto, nunca como HTML)."""
    anio: int
    mes: int
    observaciones: list[str]  # de 0 a 3 frases cortas
    consejo: str              # puede ser ""
    sin_datos: bool = False   # el mes no tiene movimientos: no se llamó a Gemini
