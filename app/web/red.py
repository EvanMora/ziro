"""La IP del visitante, para los límites de intentos (app/api/auth.py).

En Vercel la app está detrás de su red: la IP de la conexión es la de Vercel, la misma para todos.
La real llega en la cabecera x-vercel-forwarded-for, que Vercel sobrescribe en cada petición, así
que el visitante no la puede falsificar. Fuera de Vercel no se lee ninguna cabecera: cualquiera
podría mandarla con otra IP para esquivar el límite.
"""
from fastapi import Request

from app.config import en_vercel


def ip_cliente(request: Request) -> str:
    if en_vercel():
        primera = request.headers.get("x-vercel-forwarded-for", "").split(",")[0].strip()
        if primera:
            return primera
    return request.client.host if request.client else "desconocida"
