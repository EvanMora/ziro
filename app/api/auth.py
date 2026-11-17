"""Auth: registro, inicio y cierre de sesión.

Al registrarse o entrar se abre una sesión nueva (app/web/sesion.py). El login y el registro tienen
límite de intentos (app/services/limites.py): 5 fallos por correo y por IP en 15 minutos para entrar,
5 registros por IP por hora. Pasado el límite responden 429.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.schemas.auth import LoginEntrada, RegistroEntrada
from app.services import limites, usuarios
from app.services.comun import ErrorValidacion
from app.web.red import ip_cliente
from app.web.sesion import abrir_sesion, cerrar_sesion

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

DEMASIADOS_INTENTOS = "Hiciste demasiados intentos. Espera unos minutos antes de volver a intentar."


def _ip(request: Request) -> str:
    return f"ip:{ip_cliente(request)}"


def _demasiados() -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": DEMASIADOS_INTENTOS})


@router.post("/registro")
def registrar(payload: RegistroEntrada, request: Request) -> JSONResponse:
    """Crea el usuario (con las validaciones de services/usuarios.py) y abre su sesión."""
    ip = _ip(request)
    if limites.REGISTRO.bloqueado(ip):
        return _demasiados()
    limites.REGISTRO.registrar(ip)
    try:
        usuario = usuarios.crear(nombre=payload.nombre, email=payload.email, password=payload.password)
    except ErrorValidacion as error:
        # Errores por campo para que el formulario los muestre bajo cada input.
        return JSONResponse(status_code=422, content={"errores": error.errores})
    abrir_sesion(request, usuario.id, recordar=False)
    return JSONResponse(status_code=201, content=usuarios.a_sesion(usuario).model_dump(mode="json"))


@router.post("/login")
def login(payload: LoginEntrada, request: Request) -> JSONResponse:
    """Valida el correo y la contraseña; si son buenos, abre la sesión (cookie)."""
    claves = (f"correo:{usuarios.normalizar_email(payload.email)}", _ip(request))
    if any(limites.LOGIN.bloqueado(clave) for clave in claves):
        return _demasiados()
    usuario = usuarios.verificar(payload.email, payload.password)
    if usuario is None:
        for clave in claves:
            limites.LOGIN.registrar(clave)
        # Mismo mensaje si falla el correo o la contraseña: no se dice cuál.
        return JSONResponse(status_code=401, content={"detail": "Correo o contraseña incorrectos."})
    limites.LOGIN.limpiar(claves[0])
    abrir_sesion(request, usuario.id, recordar=payload.recordar)
    return JSONResponse(status_code=200, content=usuarios.a_sesion(usuario).model_dump(mode="json"))


@router.post("/logout")
def logout(request: Request) -> JSONResponse:
    """Borra la sesión."""
    cerrar_sesion(request)
    return JSONResponse(status_code=200, content={"detail": "Sesión cerrada."})
