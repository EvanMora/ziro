"""Contratos del asistente con Gemini.

- Movimientos: el usuario escribe algo como "ayer gasté 45.000 en taxi con efectivo"; Gemini lo
  interpreta y la API devuelve un MovimientoSugerido. Es solo una sugerencia: el diálogo la muestra
  en el formulario y el usuario la revisa y guarda como siempre (POST /api/v1/movimientos).
- Resumen: AnalisisMes, observaciones y un consejo sobre las cifras del mes.
- Categorías: OrdenOtros, grupos de movimientos de "Otros" con la categoría a la que pasarlos. Nada
  cambia hasta que el usuario acepta un grupo (OrdenAplicado).
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.movimientos import CategoriaRef, Tipo

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


class MovimientoPorOrdenar(BaseModel):
    id: int
    descripcion: str


class GrupoOrden(BaseModel):
    """Movimientos de "Otros" que irían juntos a una categoría: una que ya existe (categoria) o una
    nueva (categoria_nueva, el nombre; se crea solo si el usuario acepta el grupo)."""
    tipo: Tipo
    categoria: CategoriaRef | None = None
    categoria_nueva: str | None = None
    movimientos: list[MovimientoPorOrdenar]


class OrdenOtros(BaseModel):
    anio: int
    mes: int
    revisados: int        # movimientos de "Otros" del mes con descripción (los que vio Gemini)
    sin_descripcion: int  # los de "Otros" sin descripción: no se revisan
    grupos: list[GrupoOrden]
    quedan: list[MovimientoPorOrdenar]  # revisados que no encajan en nada: se quedan en "Otros"


class OrdenAplicado(BaseModel):
    categoria: CategoriaRef  # a donde quedaron (la nueva, si se creó)
    movidos: int
