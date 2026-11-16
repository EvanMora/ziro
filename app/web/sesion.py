"""El usuario de la sesión (cookie firmada por la SessionMiddleware, ver app/main.py).

Las páginas web llevan a /login si no hay sesión y las APIs responden 401. Con sesión, todos los
servicios trabajan para ese usuario: las pantallas leen y escriben solo sus datos.
"""
from fastapi import Request

from app.schemas.auth import UsuarioSesion
from app.services import usuarios


def usuario_actual(request: Request) -> UsuarioSesion | None:
    """El usuario guardado en la sesión, o None sin sesión (o con un id que ya no existe)."""
    id_ = request.session.get("usuario_id")
    if not isinstance(id_, int) or isinstance(id_, bool):
        # false/true llegan como bool en JSON; un id de verdad es int. Cualquier otra cosa no es sesión.
        return None
    usuario = usuarios.obtener(id_)
    if usuario is None:
        request.session.clear()  # sesión huérfana: el usuario ya no existe
        return None
    return usuarios.a_sesion(usuario)
