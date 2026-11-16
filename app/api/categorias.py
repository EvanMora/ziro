"""API JSON de categorías. La usa el diálogo de la sección Categorías con fetch. Igual que la de
movimientos, los errores de validación llegan como {"errores": {campo: mensaje}}.

- 403 si se intenta cambiar o eliminar una categoría predeterminada.
- DELETE recibe ?mover_a=<id> cuando la categoría tiene movimientos (ver services/categorias.py).
"""
import re
from typing import Any

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.schemas.categorias import Categoria, CategoriaEntrada
from app.services import categorias as servicio
from app.api.comun import usuario_requerido
from app.services.comun import ErrorValidacion, NoEncontrado, NoPermitido

router = APIRouter(prefix="/api/v1/categorias", tags=["categorias"])

_MENSAJES_FORMA = {
    "nombre": "Escribe un nombre.",
    "tipo": "Elige gasto o ingreso.",
}
_PREDETERMINADA = "Las categorías predeterminadas no se pueden cambiar ni eliminar."


def _errores(errores: dict[str, str], status_code: int = 422) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"errores": errores})


def _no_existe() -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "No existe"})


def _entrada(cuerpo: Any) -> CategoriaEntrada | JSONResponse:
    if not isinstance(cuerpo, dict):
        return _errores({"general": "Los datos no tienen el formato esperado."})
    try:
        return CategoriaEntrada.model_validate(cuerpo)
    except ValidationError as error:
        errores: dict[str, str] = {}
        for detalle in error.errors():
            campo = str(detalle["loc"][0]) if detalle["loc"] else "general"
            errores.setdefault(campo, _MENSAJES_FORMA.get(campo, "Dato no válido."))
        return _errores(errores)


@router.get("", response_model=list[Categoria])
def listar(usuario: int = Depends(usuario_requerido)):
    return servicio.listar(usuario)


@router.post("", response_model=Categoria, status_code=201)
def crear(cuerpo: Any = Body(None), usuario: int = Depends(usuario_requerido)):
    entrada = _entrada(cuerpo)
    if isinstance(entrada, JSONResponse):
        return entrada
    try:
        return servicio.crear(usuario, entrada)
    except ErrorValidacion as error:
        return _errores(error.errores)


@router.put("/{id}", response_model=Categoria)
def actualizar(id: int, cuerpo: Any = Body(None), usuario: int = Depends(usuario_requerido)):
    entrada = _entrada(cuerpo)
    if isinstance(entrada, JSONResponse):
        return entrada
    try:
        return servicio.actualizar(usuario, id, entrada)
    except NoEncontrado:
        return _no_existe()
    except NoPermitido:
        return _errores({"general": _PREDETERMINADA}, 403)
    except ErrorValidacion as error:
        return _errores(error.errores)


@router.delete("/{id}", status_code=204)
def eliminar(id: int, mover_a: str | None = None, usuario: int = Depends(usuario_requerido)):
    # mover_a llega como texto para responder con el mensaje del campo, no con el 422 de FastAPI.
    destino = None
    if mover_a:
        if not re.fullmatch(r"[0-9]{1,9}", mover_a):
            return _errores({"mover_a": "Elige otra categoría."})
        destino = int(mover_a)
    try:
        servicio.eliminar(usuario, id, destino)
    except NoEncontrado:
        return _no_existe()
    except NoPermitido:
        return _errores({"general": _PREDETERMINADA}, 403)
    except ErrorValidacion as error:
        return _errores(error.errores)
    return Response(status_code=204)
