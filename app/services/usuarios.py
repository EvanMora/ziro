"""Usuarios: credenciales de correo y contraseña.

Por ahora guarda todo en memoria del proceso (se pierde al reiniciar). TODO(backend): tabla Usuario
con google_sub único, password_hash nullable y foto_url; el login con Google la busca por
google_sub, el resto de consultas por usuario_id.
"""
import hashlib
import hmac
from datetime import datetime, timezone

from app.schemas.auth import UsuarioSesion
from app.schemas.usuarios import Usuario

_usuarios: dict[int, Usuario] = {}
_siguiente_id = 1


def reiniciar() -> None:
    """Vacía el almacén. Solo para tests."""
    global _siguiente_id
    _usuarios.clear()
    _siguiente_id = 1


def _nuevo_id() -> int:
    global _siguiente_id
    _siguiente_id += 1
    return _siguiente_id - 1


def _hash(password: str) -> str:
    """Hash de la contraseña guardado para comparar (TODO(backend): con un algoritmo correcto)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def crear(email: str, password: str, nombre: str = "") -> Usuario:
    """Crea un usuario con correo y contraseña (alta con registro). El password se guarda hasheado."""
    usuario = Usuario(
        id=_nuevo_id(),
        nombre=nombre or email,
        email=email,
        password_hash=_hash(password),
        creado_en=datetime.now(timezone.utc),
    )
    _usuarios[usuario.id] = usuario
    return usuario


def buscar_por_email(email: str) -> Usuario | None:
    """El usuario por su correo. Para el login con Google se busca por google_sub, no por correo."""
    return next((u for u in _usuarios.values() if u.email == email), None)


def obtener(id: int) -> Usuario | None:
    """El usuario por su id de la sesión."""
    return _usuarios.get(id)


def verificar(email: str, password: str) -> Usuario | None:
    """La cruza contra la contraseña hasheada. None si no existe el correo o la contraseña no
    coincide: no se filtra cuál falló."""
    usuario = buscar_por_email(email)
    if usuario is None or usuario.password_hash is None:
        return None
    if not hmac.compare_digest(_hash(password), usuario.password_hash):
        return None
    return usuario


def a_sesion(usuario: Usuario) -> UsuarioSesion:
    """La forma que leen las plantillas y la API de la sesión: id, nombre, correo e iniciales."""
    iniciales = "".join(palabra[:1].upper() for palabra in usuario.nombre.split() if palabra.strip())
    return UsuarioSesion(
        id=usuario.id,
        nombre=usuario.nombre,
        correo=usuario.email,
        iniciales=iniciales or usuario.email[:2].upper(),
        foto_url=usuario.foto_url,
    )
