"""Contrato del login: lo que entra por el formulario y lo que devuelve la sesión."""
from pydantic import BaseModel


class LoginEntrada(BaseModel):
    """Cuerpo del POST /api/v1/auth/login. "recordar" es el checkbox del formulario."""
    email: str
    password: str
    recordar: bool = False


class UsuarioSesion(BaseModel):
    """El usuario con la sesión lista, en la forma que leen las plantillas y la API: id, nombre,
    correo e iniciales."""

    id: int
    nombre: str
    correo: str
    iniciales: str
    foto_url: str | None = None
