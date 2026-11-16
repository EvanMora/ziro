"""La sesión del usuario: abrirla al entrar, cerrarla y saber quién está en cada petición.

La cookie la firma la SessionMiddleware de Starlette (app/main.py) y guarda solo el id del usuario y
cuándo vence. El vencimiento lo revisa el servidor: «Recordarme» la deja 30 días; sin marcar, 12 horas.

Todas las páginas y la API dependen de usuario_actual(); sin una sesión válida lanza SinSesion, que
app/main.py responde con 303 a /login en las páginas y 401 en /api/.
"""
from datetime import datetime, timedelta, timezone

from fastapi import Request

from app.schemas.auth import UsuarioSesion
from app.services import usuarios

DURACION_RECORDAR = timedelta(days=30)
DURACION_NORMAL = timedelta(hours=12)


class SinSesion(Exception):
    """No hay una sesión válida: falta, venció, está mal formada o el usuario ya no existe."""


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def abrir_sesion(request: Request, usuario_id: int, recordar: bool) -> None:
    """Empieza una sesión nueva: lo que hubiera antes se borra (contra la fijación de sesión)."""
    duracion = DURACION_RECORDAR if recordar else DURACION_NORMAL
    request.session.clear()
    request.session["usuario_id"] = usuario_id
    request.session["expira"] = (ahora() + duracion).timestamp()


def cerrar_sesion(request: Request) -> None:
    request.session.clear()


def usuario_opcional(request: Request) -> UsuarioSesion | None:
    """El usuario de la sesión, o None. Una sesión inválida se borra para no revisarla otra vez."""
    usuario_id = request.session.get("usuario_id")
    expira = request.session.get("expira")
    valida = (type(usuario_id) is int and isinstance(expira, (int, float)) and not isinstance(expira, bool)
              and ahora().timestamp() < expira)
    usuario = usuarios.obtener(usuario_id) if valida else None
    if usuario is None:
        if request.session:
            request.session.clear()
        return None
    return usuarios.a_sesion(usuario)


def usuario_actual(request: Request) -> UsuarioSesion:
    """Dependencia de FastAPI para todo lo que exige haber iniciado sesión."""
    usuario = usuario_opcional(request)
    if usuario is None:
        raise SinSesion()
    return usuario
