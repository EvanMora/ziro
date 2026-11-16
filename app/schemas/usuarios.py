"""Contrato del usuario entre los services, la API y las plantillas.

Un usuario puede entrar con correo y contraseña (password_hash) o con Google (google_sub, sin
password: quien entra con Google no tiene). El correo puede cambiar, por eso el login con Google
busca por google_sub y no por correo.
"""
from datetime import datetime

from pydantic import BaseModel


class Usuario(BaseModel):
    id: int
    nombre: str
    email: str
    password_hash: str | None = None  # null: quien entra con Google no tiene contraseña
    google_sub: str | None = None  # id del usuario en Google, único
    foto_url: str | None = None  # picture de Google
    creado_en: datetime
