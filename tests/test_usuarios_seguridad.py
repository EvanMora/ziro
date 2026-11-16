"""Seguridad de las credenciales: hash Argon2id, migración de hashes SHA-256 viejos y validación del
registro en el servidor (docs/superpowers/specs/2026-11-16-crear-cuenta-design.md, secciones 2 y 3)."""
import hashlib
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.usuarios import UsuarioDB
from app.services import database, usuarios
from app.services.comun import ErrorValidacion

pytestmark = pytest.mark.sin_plantilla


def _hash_guardado(email: str) -> str:
    with database.sesion() as db:
        return db.execute(select(UsuarioDB.password_hash).where(UsuarioDB.email == email)).scalar_one()


def _insertar(email: str, password_hash: str) -> None:
    with database.sesion() as db:
        db.add(UsuarioDB(nombre="Viejo", email=email, password_hash=password_hash,
                         creado_en=datetime.now(timezone.utc)))


def test_el_hash_es_argon2id():
    usuarios.crear("ana@x.com", "secreta123", "Ana")

    assert _hash_guardado("ana@x.com").startswith("$argon2id$")


def test_hash_sha256_viejo_entra_y_se_convierte():
    viejo = hashlib.sha256(b"secreta123").hexdigest()
    _insertar("viejo@x.com", viejo)

    assert usuarios.verificar("viejo@x.com", "otra-cosa") is None
    assert _hash_guardado("viejo@x.com") == viejo

    assert usuarios.verificar("viejo@x.com", "secreta123") is not None
    assert _hash_guardado("viejo@x.com").startswith("$argon2id$")
    # Y con el hash nuevo sigue entrando.
    assert usuarios.verificar("viejo@x.com", "secreta123") is not None


def test_correo_se_normaliza_al_crear_y_al_entrar():
    usuarios.crear("  Ana@X.COM ", "secreta123", "Ana")

    assert usuarios.buscar_por_email("ana@x.com").email == "ana@x.com"
    assert usuarios.verificar(" ANA@x.com", "secreta123") is not None


def test_correo_repetido_sin_importar_mayusculas():
    usuarios.crear("ana@x.com", "secreta123", "Ana")

    with pytest.raises(ErrorValidacion) as error:
        usuarios.crear("ANA@x.com", "secreta123", "Ana")
    assert "email" in error.value.errores


def test_correo_viejo_con_mayusculas_se_encuentra():
    _insertar("Ana@X.com", hashlib.sha256(b"secreta123").hexdigest())

    assert usuarios.buscar_por_email("ana@x.com") is not None
    assert usuarios.verificar("ana@x.com", "secreta123") is not None


@pytest.mark.parametrize(("nombre", "email", "password", "campo"), [
    ("", "ana@x.com", "secreta123", "nombre"),
    ("   ", "ana@x.com", "secreta123", "nombre"),
    ("a" * 101, "ana@x.com", "secreta123", "nombre"),
    ("Ana", "", "secreta123", "email"),
    ("Ana", "no-es-correo", "secreta123", "email"),
    ("Ana", "a@b", "secreta123", "email"),
    ("Ana", "x" * 250 + "@x.co", "secreta123", "email"),
    ("Ana", "ana@x.com", "1234567", "password"),
    ("Ana", "ana@x.com", "x" * 129, "password"),
])
def test_validaciones_del_registro(nombre, email, password, campo):
    with pytest.raises(ErrorValidacion) as error:
        usuarios.crear(email=email, password=password, nombre=nombre)
    assert campo in error.value.errores


def test_varios_errores_a_la_vez():
    with pytest.raises(ErrorValidacion) as error:
        usuarios.crear(email="malo", password="corta", nombre="")
    assert set(error.value.errores) == {"nombre", "email", "password"}


@pytest.mark.parametrize("password", ["x" * 8, "x" * 128])
def test_contrasena_de_8_y_de_128_se_aceptan(password):
    usuario = usuarios.crear("ana@x.com", password, "Ana")

    assert usuarios.verificar("ana@x.com", password).id == usuario.id


def test_nombre_se_guarda_sin_espacios_sobrantes():
    assert usuarios.crear("ana@x.com", "secreta123", "  Ana Gómez ").nombre == "Ana Gómez"


def test_carrera_de_registro_da_422(monkeypatch):
    usuarios.crear("ana@x.com", "secreta123", "Ana")
    # Simula que otra petición insertó el mismo correo entre el chequeo y el INSERT.
    monkeypatch.setattr(usuarios, "buscar_por_email", lambda email: None)

    with pytest.raises(ErrorValidacion) as error:
        usuarios.crear("ana@x.com", "secreta123", "Ana")
    assert "email" in error.value.errores


def test_login_sin_usuario_igual_verifica_un_hash(monkeypatch):
    llamadas = []
    original = usuarios._coincide

    def contar(password_hash, password):
        llamadas.append(password_hash)
        return original(password_hash, password)

    monkeypatch.setattr(usuarios, "_coincide", contar)

    assert usuarios.verificar("nadie@x.com", "secreta123") is None
    assert llamadas == [usuarios._HASH_FALSO]


def test_contrasena_enorme_en_el_login_no_entra():
    usuarios.crear("ana@x.com", "secreta123", "Ana")

    assert usuarios.verificar("ana@x.com", "secreta123" + "x" * 10_000) is None
