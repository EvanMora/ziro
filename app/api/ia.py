"""API del asistente con Gemini. Mismo formato de errores que la API de movimientos:
{"errores": {campo: mensaje}}. 422: datos no válidos · 429: pasó el límite de consultas (con
Retry-After) · 503: Gemini no configurado o no disponible.

- POST /interpretar-movimiento: frase → movimiento sugerido (diálogo y menú de Movimientos).
- GET /analisis-mes: observaciones y consejo sobre un mes (menú del Resumen)."""
from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse

from app.schemas.ia import MAX_TEXTO, AnalisisMes, MovimientoSugerido
from app.schemas.auth import UsuarioSesion
from app.services import ia as servicio
from app.services import movimientos as movimientos_servicio
from app.web.sesion import usuario_actual

router = APIRouter(prefix="/api/v1/ia", tags=["ia"])


def _errores(status: int, errores: dict[str, str]) -> JSONResponse:
    return JSONResponse(status_code=status, content={"errores": errores})


@router.post("/interpretar-movimiento", response_model=MovimientoSugerido)
def interpretar_movimiento(cuerpo: Any = Body(None), usuario: UsuarioSesion = Depends(usuario_actual)):
    texto = cuerpo.get("texto") if isinstance(cuerpo, dict) else None
    if not isinstance(texto, str) or not texto.strip():
        return _errores(422, {"texto": "Escribe qué gastaste o recibiste."})
    if len(texto) > MAX_TEXTO:
        return _errores(422, {"texto": f"Máximo {MAX_TEXTO} caracteres."})
    if not servicio.configurado():
        return _errores(503, {"general": "El asistente no está configurado."})
    return _llamar(servicio.interpretar, usuario.id, texto)


@router.get("/analisis-mes", response_model=AnalisisMes)
def analisis_mes(anio: str | None = Query(None), mes: str | None = Query(None),
                 usuario: UsuarioSesion = Depends(usuario_actual)):
    try:
        anio_n, mes_n = int(anio or ""), int(mes or "")
    except ValueError:
        return _errores(422, {"general": "Mes no válido."})
    hoy = movimientos_servicio.hoy()
    if not (2000 <= anio_n <= 2100 and 1 <= mes_n <= 12) or (anio_n, mes_n) > (hoy.year, hoy.month):
        return _errores(422, {"general": "Mes no válido."})
    if not servicio.configurado():
        return _errores(503, {"general": "El asistente no está configurado."})
    return _llamar(servicio.analizar_mes, usuario.id, anio_n, mes_n)


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
