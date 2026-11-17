"""Usuarios: credenciales de correo y contraseña, guardadas en la base de datos SQLite.

docs/alcance.md:
    Usuario (id, nombre, email, password_hash, creado_en)
    Adicionalmente incluye google_sub y foto_url para soportar inicio de sesión con Google.

El alta (crear) inserta en la tabla `usuarios` (motor SQLAlchemy en app/services/database.py, modelo
en app/models/usuarios.py). El login con Google busca por google_sub, el resto de consultas por
correo. Ver docs/alcance.md: las reglas de negocio viven en services/.

Seguridad (docs/superpowers/specs/2026-11-16-crear-cuenta-design.md):
- La contraseña se guarda con Argon2id (argon2-cffi, parámetros recomendados por OWASP); la sal va
  dentro del hash. Los hashes SHA-256 de antes se aceptan una vez y se reemplazan por Argon2id.
- Si el correo no existe se verifica igual contra un hash falso: la respuesta tarda lo mismo y no
  revela qué correos están registrados.
- El correo se guarda y se busca en minúsculas y sin espacios; nombre, correo y contraseña se validan
  aquí, no solo en el navegador.
"""
import hashlib
import hmac
from datetime import datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.models.usuarios import UsuarioDB
from app.schemas.auth import UsuarioSesion
from app.schemas.usuarios import Usuario
from app.services import database
from app.services.comun import ErrorValidacion, limpiar_texto


def reiniciar() -> None:
    """Vacía la tabla de usuarios. Solo para tests."""
    database.reiniciar()


MIN_PASSWORD = 8
MAX_PASSWORD = 128  # tope: una contraseña enorme haría gastar CPU al hashearla
MAX_NOMBRE = 100  # el largo de la columna
MAX_EMAIL = 254

_hasher = PasswordHasher()
# Para verificar algo cuando el correo no existe (mismo costo que un login real).
_HASH_FALSO = _hasher.hash("contraseña-que-no-existe")


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def _sha256(password: str) -> str:
    """El hash de antes (sin sal). Solo para reconocer y migrar los que quedan guardados."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _validar(nombre: str, email: str, password: str) -> dict[str, str]:
    errores = {}
    if not nombre:
        errores["nombre"] = "Escribe tu nombre."
    elif len(nombre) > MAX_NOMBRE:
        errores["nombre"] = f"El nombre puede tener hasta {MAX_NOMBRE} caracteres."
    if not email:
        errores["email"] = "Escribe tu correo electrónico."
    else:
        try:
            if len(email) > MAX_EMAIL:
                raise EmailNotValidError("demasiado largo")
            validate_email(email, check_deliverability=False)
        except EmailNotValidError:
            errores["email"] = "Revisa el correo. Debe verse así: nombre@correo.com"
    if len(password) < MIN_PASSWORD:
        errores["password"] = f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres."
    elif len(password) > MAX_PASSWORD:
        errores["password"] = f"La contraseña puede tener hasta {MAX_PASSWORD} caracteres."
    return errores


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


_CORREO_REPETIDO = {"email": "Ese correo ya está registrado."}


def crear(email: str, password: str, nombre: str = "") -> Usuario:
    """Crea un usuario con correo y contraseña (alta con registro). Lanza ErrorValidacion con todos
    los errores por campo (nombre, email, password)."""
    nombre, email = limpiar_texto(nombre), normalizar_email(email)
    errores = _validar(nombre, email, password)
    if errores:
        raise ErrorValidacion(errores)
    if buscar_por_email(email) is not None:
        raise ErrorValidacion(_CORREO_REPETIDO)
    password_hash = _hasher.hash(password)
    try:
        with database.sesion() as db:
            usuario_db = UsuarioDB(nombre=nombre, email=email, password_hash=password_hash,
                                   creado_en=datetime.now(timezone.utc))
            db.add(usuario_db)
            db.flush()
            return _como_usuario(usuario_db)
    except IntegrityError:
        # Otra petición registró el mismo correo entre el chequeo y el INSERT (correo único).
        raise ErrorValidacion(_CORREO_REPETIDO) from None


def buscar_por_email(email: str) -> Usuario | None:
    """El usuario por su correo. Para el login con Google se busca por google_sub, no por correo."""
    if "\x00" in email:
        return None  # ningún correo registrado lo tiene, y Postgres no acepta ese carácter en una consulta
    with database.sesion() as db:
        usuario_db = db.execute(
            select(UsuarioDB).where(func.lower(UsuarioDB.email) == normalizar_email(email))
        ).scalars().first()
        return _como_usuario(usuario_db)


def obtener(id: int) -> Usuario | None:
    """El usuario por su id de la sesión."""
    with database.sesion() as db:
        return _como_usuario(db.get(UsuarioDB, id))


def verificar(email: str, password: str) -> Usuario | None:
    """La cruza contra la contraseña hasheada. None si no existe el correo o la contraseña no
    coincide: no se filtra cuál falló."""
    if len(password) > MAX_PASSWORD:  # nadie pudo registrarla; no se gasta CPU en hashearla entera
        _coincide(_HASH_FALSO, password[:MAX_PASSWORD])
        return None
    usuario = buscar_por_email(email)
    if usuario is None or usuario.password_hash is None:
        _coincide(_HASH_FALSO, password)
        return None
    guardado = usuario.password_hash
    if guardado.startswith("$argon2"):
        if not _coincide(guardado, password):
            return None
        if _hasher.check_needs_rehash(guardado):
            _guardar_hash(usuario.id, _hasher.hash(password))
    else:
        if not hmac.compare_digest(_sha256(password), guardado):
            return None
        _guardar_hash(usuario.id, _hasher.hash(password))  # el SHA-256 viejo pasa a Argon2id
    return usuario


def _coincide(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _guardar_hash(usuario_id: int, password_hash: str) -> None:
    with database.sesion() as db:
        db.execute(update(UsuarioDB).where(UsuarioDB.id == usuario_id).values(password_hash=password_hash))


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
