"""API JSON de cuentas y pagos de tarjeta. La usan los diálogos de Cuentas y de Movimientos con
fetch. Igual que las otras APIs, los errores de validación llegan como {"errores": {campo: mensaje}}.

- DELETE /api/v1/cuentas/{id} recibe ?mover_a=<id> si la cuenta tiene movimientos o pagos.
- Los pagos se registran en la tarjeta (POST /api/v1/cuentas/{id}/pagos) y se editan o eliminan
  por su id (/api/v1/pagos/{id}).
- Las transferencias entre cuentas se cuelgan de este router (prefix /api/v1/cuentas) porque
  app/main.py ya lo registra y ese archivo no se puede tocar (cambia para Vercel): quedan en
  /api/v1/cuentas/transferencias.
"""
import re
from typing import Any

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from app.schemas.cuentas import Cuenta, CuentaEntrada, Pago, PagoEntrada, PanelCuentas
from app.services import cuentas as servicio
from app.api.comun import usuario_requerido
from app.services.comun import ErrorValidacion, NoEncontrado
from app.api import transferencias as api_transferencias

router = APIRouter(prefix="/api/v1/cuentas", tags=["cuentas"])
router_pagos = APIRouter(prefix="/api/v1/pagos", tags=["cuentas"])
# Sin tocar app/main.py, las rutas de este módulo ya registradas suman las de transferencias.
router.include_router(api_transferencias.router, prefix="/transferencias")

_MENSAJES_CUENTA = {
    "nombre": "Escribe un nombre.",
    "tipo": "Elige un tipo de cuenta.",
    "icono": "Elige un ícono.",
    "tono": "Elige un tono.",
    "saldo": "Escribe un saldo válido.",
    "cupo": "Escribe un cupo mayor que 0.",
    "dia_pago": "Elige un día entre 1 y 31.",
}
_MENSAJES_PAGO = {
    "monto": "Escribe un monto mayor que 0.",
    "cuenta_origen_id": "Elige de qué cuenta sale el pago.",
    "fecha": "Escribe una fecha válida.",
}


def _errores(errores: dict[str, str]) -> JSONResponse:
    return JSONResponse(status_code=422, content={"errores": errores})


def _no_existe() -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "No existe"})


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


def _ejecutar(usuario: int, funcion, *args):
    """Llama al servicio con el usuario de la sesión y traduce sus errores a respuestas."""
    try:
        return funcion(usuario, *args)
    except NoEncontrado:
        return _no_existe()
    except ErrorValidacion as error:
        return _errores(error.errores)


@router.get("", response_model=PanelCuentas)
def panel(usuario: int = Depends(usuario_requerido)):
    return servicio.panel(usuario)


@router.post("", response_model=Cuenta, status_code=201)
def crear(cuerpo: Any = Body(None), usuario: int = Depends(usuario_requerido)):
    entrada = _entrada(CuentaEntrada, _MENSAJES_CUENTA, cuerpo)
    return entrada if isinstance(entrada, JSONResponse) else _ejecutar(usuario, servicio.crear, entrada)


@router.put("/{id}", response_model=Cuenta)
def actualizar(id: int, cuerpo: Any = Body(None), usuario: int = Depends(usuario_requerido)):
    entrada = _entrada(CuentaEntrada, _MENSAJES_CUENTA, cuerpo)
    return entrada if isinstance(entrada, JSONResponse) else _ejecutar(usuario, servicio.actualizar, id, entrada)


@router.delete("/{id}", status_code=204)
def eliminar(id: int, mover_a: str | None = None, usuario: int = Depends(usuario_requerido)):
    # mover_a llega como texto para responder con el mensaje del campo, no con el 422 de FastAPI.
    destino = None
    if mover_a:
        if not re.fullmatch(r"[0-9]{1,9}", mover_a):
            return _errores({"mover_a": "Elige otra cuenta."})
        destino = int(mover_a)
    resultado = _ejecutar(usuario, servicio.eliminar, id, destino)
    return resultado if isinstance(resultado, JSONResponse) else Response(status_code=204)


@router.post("/{id}/pagos", response_model=Pago, status_code=201)
def registrar_pago(id: int, cuerpo: Any = Body(None), usuario: int = Depends(usuario_requerido)):
    entrada = _entrada(PagoEntrada, _MENSAJES_PAGO, cuerpo)
    return entrada if isinstance(entrada, JSONResponse) else _ejecutar(usuario, servicio.registrar_pago, id, entrada)


@router_pagos.put("/{id}", response_model=Pago)
def actualizar_pago(id: int, cuerpo: Any = Body(None), usuario: int = Depends(usuario_requerido)):
    entrada = _entrada(PagoEntrada, _MENSAJES_PAGO, cuerpo)
    return entrada if isinstance(entrada, JSONResponse) else _ejecutar(usuario, servicio.actualizar_pago, id, entrada)


@router_pagos.delete("/{id}", status_code=204)
def eliminar_pago(id: int, usuario: int = Depends(usuario_requerido)):
    resultado = _ejecutar(usuario, servicio.eliminar_pago, id)
    return resultado if isinstance(resultado, JSONResponse) else Response(status_code=204)
