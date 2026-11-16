"""API JSON de metas de ahorro. La usan los diálogos de la sección Metas con fetch. Igual que las otras
APIs, los errores de validación llegan como {"errores": {campo: mensaje}}.

- Los aportes y retiros se registran en la meta (POST /api/v1/metas/{id}/aportes, con retiro=true
  para retirar) y se borran por su id dentro de la meta.
"""
from typing import Any

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from app.schemas.auth import UsuarioSesion
from app.schemas.metas import Aporte, AporteEntrada, Meta, MetaEntrada, PanelMetas
from app.services import metas as servicio
from app.services.comun import ErrorValidacion, NoEncontrado
from app.web.sesion import usuario_actual

router = APIRouter(prefix="/api/v1/metas", tags=["metas"])

_MENSAJES_META = {
    "nombre": "Escribe un nombre.",
    "objetivo": "Escribe un objetivo mayor que 0.",
    "fecha_limite": "Escribe una fecha válida.",
}
_MENSAJES_APORTE = {
    "monto": "Escribe un monto mayor que 0.",
    "fecha": "Escribe una fecha válida.",
    "retiro": "Elige si es un aporte o un retiro.",
}


def _errores(errores: dict[str, str]) -> JSONResponse:
    return JSONResponse(status_code=422, content={"errores": errores})


def _entrada(modelo: type[BaseModel], mensajes: dict[str, str], cuerpo: Any):
    if not isinstance(cuerpo, dict):
        return _errores({"general": "Los datos no tienen el formato esperado."})
    try:
        return modelo.model_validate(cuerpo)
    except ValidationError as error:
        errores: dict[str, str] = {}
        for detalle in error.errors():
            campo = str(detalle["loc"][0]) if detalle["loc"] else "general"
            errores.setdefault(campo, mensajes.get(campo, "Dato no válido."))
        return _errores(errores)


def _ejecutar(usuario_id: int, funcion, *args):
    """Llama al servicio con el usuario de la sesión y traduce sus errores a respuestas."""
    try:
        return funcion(usuario_id, *args)
    except NoEncontrado:
        return JSONResponse(status_code=404, content={"detail": "No existe"})
    except ErrorValidacion as error:
        return _errores(error.errores)


def _sin_contenido(resultado):
    return resultado if isinstance(resultado, JSONResponse) else Response(status_code=204)


@router.get("", response_model=PanelMetas)
def panel(usuario: UsuarioSesion = Depends(usuario_actual)):
    return servicio.panel(usuario.id)


@router.post("", response_model=Meta, status_code=201)
def crear(cuerpo: Any = Body(None), usuario: UsuarioSesion = Depends(usuario_actual)):
    entrada = _entrada(MetaEntrada, _MENSAJES_META, cuerpo)
    return entrada if isinstance(entrada, JSONResponse) else _ejecutar(usuario.id, servicio.crear, entrada)


@router.put("/{id}", response_model=Meta)
def actualizar(id: int, cuerpo: Any = Body(None), usuario: UsuarioSesion = Depends(usuario_actual)):
    entrada = _entrada(MetaEntrada, _MENSAJES_META, cuerpo)
    return entrada if isinstance(entrada, JSONResponse) else _ejecutar(usuario.id, servicio.actualizar, id, entrada)


@router.delete("/{id}", status_code=204)
def eliminar(id: int, usuario: UsuarioSesion = Depends(usuario_actual)):
    return _sin_contenido(_ejecutar(usuario.id, servicio.eliminar, id))


@router.post("/{id}/aportes", response_model=Aporte, status_code=201)
def aportar(id: int, cuerpo: Any = Body(None), usuario: UsuarioSesion = Depends(usuario_actual)):
    entrada = _entrada(AporteEntrada, _MENSAJES_APORTE, cuerpo)
    return entrada if isinstance(entrada, JSONResponse) else _ejecutar(usuario.id, servicio.aportar, id, entrada)


@router.delete("/{id}/aportes/{aporte_id}", status_code=204)
def eliminar_aporte(id: int, aporte_id: int, usuario: UsuarioSesion = Depends(usuario_actual)):
    return _sin_contenido(_ejecutar(usuario.id, servicio.eliminar_aporte, id, aporte_id))
