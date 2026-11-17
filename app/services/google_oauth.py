"""Google OAuth (Authlib) cliente para inicio de sesión con Google."""
import os
from authlib.integrations.starlette_client import OAuth

# OAuth cliente global
_oauth = OAuth()


def configurado() -> bool:
    """Devuelve True si hay client_id y client_secret en el entorno."""
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))


def cliente():
    """Devuelve el cliente OAuth de Google registrado; None si no está configurado."""
    if not configurado():
        return None
    # Registrar con los valores actuales; registrar varias veces es seguro (sobrescribe)
    _oauth.register(
        "google",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    return _oauth.google