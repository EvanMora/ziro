"""Lo que comparten los servicios: los errores que la API traduce a respuestas, la limpieza de
textos escritos por la persona y la comparación sin tildes ni mayúsculas."""
import unicodedata


class ErrorValidacion(Exception):
    """Errores por campo: {campo: mensaje}. La API responde 422 con {"errores": ...}."""

    def __init__(self, errores: dict[str, str]):
        super().__init__(errores)
        self.errores = errores


class NoEncontrado(Exception):
    pass


class NoPermitido(Exception):
    """Existe, pero el usuario no lo puede cambiar (p. ej. una categoría predeterminada)."""


_UNION = "\u200d"  # une emojis (👨‍👩‍👧): se conserva


def _sin_invisibles(texto: str, dejar_union: bool) -> str:
    """Quita los caracteres de formato invisibles (categoría Unicode Cf: espacio de ancho cero,
    BOM, guion suave, unión de palabras...)."""
    return "".join(c for c in texto if (dejar_union and c == _UNION) or unicodedata.category(c) != "Cf")


def limpiar_texto(texto: str) -> str:
    """Nombre o descripción escritos por la persona: sin invisibles y con los espacios juntos.
    Si no queda nada visible devuelve "", así un nombre hecho solo de invisibles cuenta como vacío."""
    limpio = " ".join(_sin_invisibles(texto, dejar_union=True).split())
    return limpio if limpio.replace(_UNION, "").strip() else ""


def normalizar(texto: str) -> str:
    """Para comparar: sin invisibles, sin tildes y sin mayúsculas."""
    sin_tildes = unicodedata.normalize("NFKD", _sin_invisibles(texto, dejar_union=False))
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).casefold()
