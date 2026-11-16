"""Base declarativa compartida por todas las tablas de la aplicación."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
