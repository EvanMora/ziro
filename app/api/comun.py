"""El acceso a la sesión que comparten las APIs JSON: sin sesión, 401.

Todas las APIs de app/api/ reciben el usuario con Depends(usuario_requerido). El login crea la
sesión (app/api/auth.py); aquí solo se lee.
"""
from fastapi import HTTPException, Request

from app.web.sesion import usuario_actual


def usuario_requerido(request: Request) -> int:
    """El id del usuario de la sesión. Sin sesión: 401 con el formato {"detail": ...} de la API."""
    usuario = usuario_actual(request)
    if usuario is None:
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar.")
    return usuario.id
