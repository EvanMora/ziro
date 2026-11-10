"""API JSON de movimientos. La usa el diálogo "Nuevo movimiento" con fetch y es el contrato
con el backend: los errores de validación siempre llegan como {"errores": {campo: mensaje}}."""
from typing import Any

from fastapi import APIRouter, Body, Query, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.schemas.movimientos import (
    FiltrosMovimientos,
    ListaMovimientos,
    Movimiento,
    MovimientoEntrada,
    Tipo,
)
from app.services import movimientos as servicio
from app.web.sesion import USUARIO_DEMO

router = APIRouter(prefix="/api/v1/movimientos", tags=["movimientos"])

# Un mensaje por campo cuando el dato ni siquiera tiene la forma correcta (texto en vez de número, etc.).
_MENSAJES_FORMA = {
    "tipo": "Elige gasto o ingreso.",
    "monto": "Escribe un monto mayor que 0.",
    "categoria_id": "Elige una categoría.",
    "cuenta_id": "Elige una cuenta.",
    "fecha": "Escribe una fecha válida.",
    "descripcion": "Escribe una descripción válida.",
}


def _errores(errores: dict[str, str]) -> JSONResponse:
    return JSONResponse(status_code=422, content={"errores": errores})


def _entrada(cuerpo: Any) -> MovimientoEntrada | JSONResponse:
    if not isinstance(cuerpo, dict):
        return _errores({"general": "Los datos no tienen el formato esperado."})
    try:
        return MovimientoEntrada.model_validate(cuerpo)
    except ValidationError as error:
        errores: dict[str, str] = {}
        for detalle in error.errors():
            campo = str(detalle["loc"][0]) if detalle["loc"] else "general"
            errores.setdefault(campo, _MENSAJES_FORMA.get(campo, "Dato no válido."))
        return _errores(errores)


def _usuario() -> int:
    return USUARIO_DEMO["id"]


@router.get("", response_model=ListaMovimientos)
def listar(
    anio: int = Query(ge=2000, le=2100),
    mes: int = Query(ge=1, le=12),
    tipo: Tipo | None = None,
    cuenta_id: int | None = None,
    categoria_id: int | None = None,
    q: str | None = None,
):
    filtros = FiltrosMovimientos(tipo=tipo, cuenta_id=cuenta_id, categoria_id=categoria_id, q=q)
    return servicio.listar(_usuario(), anio, mes, filtros)


@router.post("", response_model=Movimiento, status_code=201)
def crear(cuerpo: Any = Body(None)):
    entrada = _entrada(cuerpo)
    if isinstance(entrada, JSONResponse):
        return entrada
    try:
        return servicio.crear(_usuario(), entrada)
    except servicio.ErrorValidacion as error:
        return _errores(error.errores)


@router.put("/{id}", response_model=Movimiento)
def actualizar(id: int, cuerpo: Any = Body(None)):
    entrada = _entrada(cuerpo)
    if isinstance(entrada, JSONResponse):
        return entrada
    try:
        return servicio.actualizar(_usuario(), id, entrada)
    except servicio.NoEncontrado:
        return JSONResponse(status_code=404, content={"detail": "No existe"})
    except servicio.ErrorValidacion as error:
        return _errores(error.errores)


@router.delete("/{id}", status_code=204)
def eliminar(id: int):
    try:
        servicio.eliminar(_usuario(), id)
    except servicio.NoEncontrado:
        return JSONResponse(status_code=404, content={"detail": "No existe"})
    return Response(status_code=204)
