"""API JSON de transferencias entre cuentas de dinero. La usan los diálogos de Cuentas (y la
futura pantalla de historial) con fetch. Igual que las otras APIs, los errores de validación llegan
como {"errores": {campo: mensaje}}.

La plata pasa de una cuenta de dinero a otra: no es un gasto ni un ingreso, solo cambia de cuenta
(igual que los pagos de tarjeta mueven plata entre una cuenta y una tarjeta).

Nota: este router no tiene prefix propio: app/api/cuentas.py lo monta en /api/v1/cuentas/transferencias
porque app/main.py registra ese router y no se puede tocar (cambia para Vercel).
"""
from typing import Any

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from app.schemas.cuentas import Transferencia, TransferenciaEntrada
from app.services import cuentas as servicio
from app.api.comun import usuario_requerido
from app.services.comun import ErrorValidacion, NoEncontrado

router = APIRouter(tags=["transferencias"])

_MENSAJES_TRANSFERENCIA = {
    "monto": "Escribe un monto mayor que 0.",
    "cuenta_origen_id": "Elige una cuenta de dinero de dónde sale.",
    "cuenta_destino_id": "Elige una cuenta de dinero a dónde va.",
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


@router.get("", response_model=list[Transferencia])
def listar(usuario: int = Depends(usuario_requerido)):
    return servicio.listar_transferencias(usuario)


@router.post("", response_model=Transferencia, status_code=201)
def registrar(cuerpo: Any = Body(None), usuario: int = Depends(usuario_requerido)):
    entrada = _entrada(TransferenciaEntrada, _MENSAJES_TRANSFERENCIA, cuerpo)
    return entrada if isinstance(entrada, JSONResponse) else _ejecutar(usuario, servicio.registrar_transferencia, entrada)


@router.get("/{id}", response_model=Transferencia)
def obtener(id: int, usuario: int = Depends(usuario_requerido)):
    transferencia = servicio.obtener_transferencia(usuario, id)
    return transferencia if transferencia is not None else _no_existe()


@router.put("/{id}", response_model=Transferencia)
def actualizar(id: int, cuerpo: Any = Body(None), usuario: int = Depends(usuario_requerido)):
    entrada = _entrada(TransferenciaEntrada, _MENSAJES_TRANSFERENCIA, cuerpo)
    return entrada if isinstance(entrada, JSONResponse) else _ejecutar(usuario, servicio.actualizar_transferencia, id, entrada)


@router.delete("/{id}", status_code=204)
def eliminar(id: int, usuario: int = Depends(usuario_requerido)):
    resultado = _ejecutar(usuario, servicio.eliminar_transferencia, id)
    return resultado if isinstance(resultado, JSONResponse) else Response(status_code=204)
