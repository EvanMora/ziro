"""API JSON de presupuestos. La usa la pantalla "Crear presupuesto" con fetch. Igual que las demás,
los errores de validación llegan como {"errores": {campo: mensaje}}; los de cada monto usan el
campo "monto_<categoria_id>".
"""
from typing import Any

from fastapi import APIRouter, Body, Depends, Path
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.schemas.presupuestos import PresupuestoDelMes, PresupuestoEntrada
from app.schemas.auth import UsuarioSesion
from app.services import presupuestos as servicio
from app.services.comun import ErrorValidacion
from app.web.sesion import usuario_actual

router = APIRouter(prefix="/api/v1/presupuestos", tags=["presupuestos"])


def _errores(errores: dict[str, str]) -> JSONResponse:
    return JSONResponse(status_code=422, content={"errores": errores})


@router.get("/{anio}/{mes}", response_model=PresupuestoDelMes)
def obtener(anio: int = Path(ge=2000, le=2100), mes: int = Path(ge=1, le=12),
            usuario: UsuarioSesion = Depends(usuario_actual)):
    return servicio.del_mes(usuario.id, anio, mes)


@router.put("/{anio}/{mes}", response_model=PresupuestoDelMes)
def guardar(anio: int = Path(ge=2000, le=2100), mes: int = Path(ge=1, le=12), cuerpo: Any = Body(None),
            usuario: UsuarioSesion = Depends(usuario_actual)):
    if not isinstance(cuerpo, dict):
        return _errores({"general": "Los datos no tienen el formato esperado."})
    try:
        entrada = PresupuestoEntrada.model_validate(cuerpo)
    except ValidationError as error:
        errores: dict[str, str] = {}
        for detalle in error.errors():
            loc = detalle["loc"]
            # ("montos", i, "monto"): se responde en el campo de esa categoría si se puede leer.
            if len(loc) >= 3 and loc[0] == "montos" and isinstance(loc[1], int):
                item = cuerpo.get("montos", [])[loc[1]]
                cid = item.get("categoria_id") if isinstance(item, dict) else None
                if isinstance(cid, int) and not isinstance(cid, bool):
                    errores.setdefault(f"monto_{cid}", "Escribe un monto válido.")
                    continue
            errores.setdefault("general", "Los datos no tienen el formato esperado.")
        return _errores(errores)
    try:
        return servicio.guardar(usuario.id, anio, mes, entrada)
    except ErrorValidacion as error:
        return _errores(error.errores)
