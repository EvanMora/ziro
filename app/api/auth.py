"""Auth: inicio y cierre de sesión. El inicio con Google (Authlib) es la otra rama de este router:
    /auth/google/login y /auth/google/callback, que guardan el id en la misma sesión."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.schemas.auth import LoginEntrada
from app.services import usuarios

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginEntrada, request: Request) -> JSONResponse:
    """Valida el correo y la contraseña; si son buenos, guarda el usuario en la sesión (cookie)."""
    usuario = usuarios.verificar(payload.email, payload.password)
    if usuario is None:
        # Mismo mensaje si falla el correo o la contraseña: no se dice cuál.
        return JSONResponse(status_code=401, content={"detail": "Correo o contraseña incorrectos."})
    request.session["usuario_id"] = usuario.id
    return JSONResponse(status_code=200, content=usuarios.a_sesion(usuario).model_dump(mode="json"))


@router.post("/logout")
def logout(request: Request) -> JSONResponse:
    """Borra la sesión y cierra el login."""
    request.session.clear()
    return JSONResponse(status_code=200, content={"detail": "Sesión cerrada."})
