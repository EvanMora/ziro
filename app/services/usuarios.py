"""Usuarios: credenciales de correo y contraseña, guardadas en la base de datos SQLite.

docs/alcance.md:
    Usuario (id, nombre, email, password_hash, creado_en)
    Adicionalmente incluye google_sub y foto_url para soportar inicio de sesión con Google.

El alta (crear) inserta en la tabla `usuarios` (motor SQLAlchemy en app/services/database.py, modelo
en app/models/usuarios.py). El login con Google busca por google_sub, el resto de consultas por
correo. Ver docs/alcance.md: las reglas de negocio viven en services/.

Contraseñas: bcrypt (con costo 12; los tests lo bajan). Las bases antiguas guardaban SHA-256 en
hex: al iniciar sesión con ellas, la contraseña se verifica y se vuelve a hashear con bcrypt en
ese mismo momento (migración transparente).
"""
import hashlib
import hmac
import re
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import select

from app.models.usuarios import UsuarioDB
from app.schemas.auth import UsuarioSesion
from app.schemas.usuarios import Usuario
from app.services import database
from app.services.comun import ErrorValidacion


def reiniciar() -> None:
    """Vacía la tabla de usuarios. Solo para tests."""
    database.reiniciar()


# Costo de bcrypt. Los tests lo bajan a 4 para que la suite no pague el costo real.
RONDAS_BCRYPT = 12
_LEGACY_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _hash(password: str) -> str:
    """Hash bcrypt de la contraseña para guardar en password_hash."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=RONDAS_BCRYPT)).decode("utf-8")


def _verificar(password: str, hash_guardado: str) -> str | None:
    """El algoritmo con el que coincide ("bcrypt", "legacy" = SHA-256 en hex) o None si no coincide."""
    if _LEGACY_SHA256.fullmatch(hash_guardado or ""):
        ok = hmac.compare_digest(hashlib.sha256(password.encode("utf-8")).hexdigest(), hash_guardado)
        return "legacy" if ok else None
    try:
        return "bcrypt" if bcrypt.checkpw(password.encode("utf-8"), hash_guardado.encode("utf-8")) else None
    except ValueError:  # hash corrupto en la base
        return None


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
    """La cruza contra el hash guardado. None si no existe el correo o la contraseña no coincide:
    no se filtra cuál falló. Si el hash era de la época SHA-256, lo sube a bcrypt al validar."""
    usuario = buscar_por_email(email)
    if usuario is None or usuario.password_hash is None:
        return None
    algoritmo = _verificar(password, usuario.password_hash)
    if algoritmo is None:
        return None
    if algoritmo == "legacy":
        # Migración transparente: la contraseña sigue siendo la misma, solo cambia el algoritmo.
        with database.sesion() as db:
            fila = db.get(UsuarioDB, usuario.id)
            if fila is not None:
                fila.password_hash = _hash(password)
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
