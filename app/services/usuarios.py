"""Usuarios: credenciales de correo y contraseña, guardadas en la base de datos SQLite.

docs/alcance.md:
    Usuario (id, nombre, email, password_hash, creado_en)
    Adicionalmente incluye google_sub y foto_url para soportar inicio de sesión con Google.

El alta (crear) inserta en la tabla `usuarios` (motor SQLAlchemy en app/services/database.py, modelo
en app/models/usuarios.py). El login con Google busca por google_sub, el resto de consultas por
correo. Ver docs/alcance.md: las reglas de negocio viven en services/.

TODO(backend): el password se guarda con un hash con algoritmo correcto (p. ej. bcrypt), no SHA-256.
"""
import hashlib
import hmac
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.usuarios import UsuarioDB
from app.schemas.auth import UsuarioSesion
from app.schemas.usuarios import Usuario
from app.services import database
from app.services.comun import ErrorValidacion


def reiniciar() -> None:
    """Vacía la tabla de usuarios. Solo para tests."""
    database.reiniciar()


def _hash(password: str) -> str:
    """Hash de la contraseña guardado para comparar (TODO(backend): con un algoritmo correcto)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _como_usuario(usuario_db: UsuarioDB | None) -> Usuario | None:
    """La fila de la base convertida al contrato que leen services, la API y las plantillas."""
    if usuario_db is None:
        return None
    return Usuario(
        id=usuario_db.id,
        nombre=usuario_db.nombre,
        email=usuario_db.email,
        password_hash=usuario_db.password_hash,
        google_sub=usuario_db.google_sub,
        foto_url=usuario_db.foto_url,
        creado_en=usuario_db.creado_en,
    )


def crear(email: str, password: str, nombre: str = "") -> Usuario:
    """Crea un usuario con correo y contraseña (alta con registro). El password se guarda hasheado."""
    with database.sesion() as db:
        duplicado = db.execute(select(UsuarioDB).where(UsuarioDB.email == email)).scalar_one_or_none()
        if duplicado is not None:
            raise ErrorValidacion({"email": "Ese correo ya está registrado."})
        usuario_db = UsuarioDB(
            nombre=nombre or email,
            email=email,
            password_hash=_hash(password),
            creado_en=datetime.now(timezone.utc),
        )
        db.add(usuario_db)
        db.flush()
        return _como_usuario(usuario_db)


def buscar_por_email(email: str) -> Usuario | None:
    """El usuario por su correo. Para el login con Google se busca por google_sub, no por correo."""
    with database.sesion() as db:
        usuario_db = db.execute(select(UsuarioDB).where(UsuarioDB.email == email)).scalars().first()
        return _como_usuario(usuario_db)


def obtener(id: int) -> Usuario | None:
    """El usuario por su id de la sesión."""
    with database.sesion() as db:
        return _como_usuario(db.get(UsuarioDB, id))


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
