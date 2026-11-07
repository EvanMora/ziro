"""API del asistente con Gemini. Mismo formato de errores que la API de movimientos:
{"errores": {campo: mensaje}}. 422: datos no válidos · 429: pasó el límite de consultas (con
Retry-After) · 503: Gemini no configurado o no disponible.

- POST /interpretar-movimiento: frase → movimiento sugerido (diálogo y menú de Movimientos).
- GET /analisis-mes: observaciones y consejo sobre un mes (menú del Resumen).
- GET /ordenar-otros: grupos de movimientos de "Otros" del mes y a dónde pasarlos (menú de Categorías).
- POST /ordenar-otros/aplicar: mueve un grupo aceptado (no llama a Gemini)."""
from typing import Any

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from app.schemas.ia import MAX_TEXTO, AnalisisMes, MovimientoSugerido, OrdenAplicado, OrdenOtros
from app.services import ia as servicio
from app.services import movimientos as movimientos_servicio
from app.services.comun import ErrorValidacion
from app.web.sesion import USUARIO_DEMO

router = APIRouter(prefix="/api/v1/ia", tags=["ia"])


def _errores(status: int, errores: dict[str, str]) -> JSONResponse:
    return JSONResponse(status_code=status, content={"errores": errores})


@router.post("/interpretar-movimiento", response_model=MovimientoSugerido)
def interpretar_movimiento(cuerpo: Any = Body(None)):
    texto = cuerpo.get("texto") if isinstance(cuerpo, dict) else None
    if not isinstance(texto, str) or not texto.strip():
        return _errores(422, {"texto": "Escribe qué gastaste o recibiste."})
    if len(texto) > MAX_TEXTO:
        return _errores(422, {"texto": f"Máximo {MAX_TEXTO} caracteres."})
    if not servicio.configurado():
        return _errores(503, {"general": "El asistente no está configurado."})
    return _llamar(servicio.interpretar, USUARIO_DEMO["id"], texto)


def _mes(anio: str | None, mes: str | None) -> tuple[int, int] | None:
    """Año y mes de la consulta, o None si no son un mes válido hasta el actual."""
    try:
        anio_n, mes_n = int(anio or ""), int(mes or "")
    except ValueError:
        return None
    hoy = movimientos_servicio.hoy()
    if not (2000 <= anio_n <= 2100 and 1 <= mes_n <= 12) or (anio_n, mes_n) > (hoy.year, hoy.month):
        return None
    return anio_n, mes_n


@router.get("/analisis-mes", response_model=AnalisisMes)
def analisis_mes(anio: str | None = Query(None), mes: str | None = Query(None)):
    periodo = _mes(anio, mes)
    if periodo is None:
        return _errores(422, {"general": "Mes no válido."})
    if not servicio.configurado():
        return _errores(503, {"general": "El asistente no está configurado."})
    return _llamar(servicio.analizar_mes, USUARIO_DEMO["id"], *periodo)


@router.get("/ordenar-otros", response_model=OrdenOtros)
def ordenar_otros(anio: str | None = Query(None), mes: str | None = Query(None)):
    periodo = _mes(anio, mes)
    if periodo is None:
        return _errores(422, {"general": "Mes no válido."})
    if not servicio.configurado():
        return _errores(503, {"general": "El asistente no está configurado."})
    return _llamar(servicio.ordenar_otros, USUARIO_DEMO["id"], *periodo)


MAX_APLICAR = 200


def _entero(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


@router.post("/ordenar-otros/aplicar", response_model=OrdenAplicado)
def aplicar_orden(cuerpo: Any = Body(None)):
    if not isinstance(cuerpo, dict):
        return _errores(422, {"general": "Datos no válidos."})
    ids = cuerpo.get("movimientos")
    if not isinstance(ids, list) or not ids or len(ids) > MAX_APLICAR or not all(map(_entero, ids)):
        return _errores(422, {"movimientos": "Elige al menos un movimiento."})
    categoria_id, nueva = cuerpo.get("categoria_id"), cuerpo.get("categoria_nueva")
    if (categoria_id is None) == (nueva is None) or (categoria_id is not None and not _entero(categoria_id)) \
            or (nueva is not None and not isinstance(nueva, str)):
        return _errores(422, {"general": "Elige una categoría existente o una nueva."})
    try:
        return servicio.aplicar_orden(USUARIO_DEMO["id"], ids, categoria_id=categoria_id, categoria_nueva=nueva)
    except ErrorValidacion as error:
        return _errores(422, error.errores)


def _llamar(funcion, *args):
    """Llama al servicio y convierte sus errores en respuestas 429 o 503."""
    try:
        return funcion(*args)
    except servicio.LimiteExcedido as error:
        respuesta = _errores(429, {"general": str(error)})
        respuesta.headers["Retry-After"] = str(error.segundos)
        return respuesta
    except servicio.ErrorIA as error:
        return _errores(503, {"general": str(error)})
