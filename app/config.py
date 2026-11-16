"""En qué entorno corre la app. Se lee de os.environ en cada llamada (no al importar), así los tests
y el .env cargado más tarde por app/main.py ven siempre el valor actual."""
import os


def en_vercel() -> bool:
    """Vercel pone la variable VERCEL en todos sus despliegues, incluidas las vistas previas."""
    return "VERCEL" in os.environ


def es_produccion() -> bool:
    """Producción: ENVIRONMENT=production o cualquier despliegue en Vercel. Ahí la cookie es Secure y
    SECRET_KEY y DATABASE_URL son obligatorias (sin disco propio, una clave al azar o una base
    SQLite serían distintas en cada instancia)."""
    return os.environ.get("ENVIRONMENT") == "production" or en_vercel()
