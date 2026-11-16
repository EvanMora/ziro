import os
import secrets
import warnings
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth as api_auth
from app.api import categorias as api_categorias
from app.api import cuentas as api_cuentas
from app.api import ia as api_ia
from app.api import movimientos as api_movimientos
from app.api import presupuestos as api_presupuestos
from app.web import views
from app.web.sesion import DURACION_RECORDAR, SinSesion, usuario_opcional

# Variables del archivo .env (p. ej. GEMINI_API_KEY). Las que ya existan en el entorno no se pisan.
load_dotenv()


class Estaticos(StaticFiles):
    """CSS, JS y fuentes con "Cache-Control: no-cache": el navegador los guarda, pero antes de usarlos
    pregunta si cambiaron (si no, el servidor responde 304 sin reenviarlos). Sin esta cabecera el
    navegador decide solo cuánto tiempo reusarlos y puede mostrar una pantalla nueva con el CSS viejo."""

    def file_response(self, *args, **kwargs):
        respuesta = super().file_response(*args, **kwargs)
        respuesta.headers["Cache-Control"] = "no-cache"
        return respuesta


def clave_secreta() -> str:
    """La clave que firma la cookie de sesión. En producción es obligatoria y larga; en desarrollo, si
    falta, se genera una al azar (las sesiones se cierran al reiniciar el servidor)."""
    clave = os.environ.get("SECRET_KEY", "")
    if os.environ.get("ENVIRONMENT") == "production":
        if len(clave) < 32:
            raise RuntimeError("SECRET_KEY es obligatoria en producción y debe tener al menos 32 caracteres.")
        return clave
    if not clave:
        warnings.warn("SECRET_KEY no está definida: se usa una clave al azar y las sesiones se cierran "
                      "al reiniciar. Defínela en el .env (ver .env.example).", stacklevel=2)
        return secrets.token_urlsafe(48)
    return clave


def sin_sesion(request: Request, exc: SinSesion):
    """Sin sesión válida: la API responde 401 y las páginas llevan al login."""
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"detail": "Inicia sesión para continuar."})
    return RedirectResponse("/login", status_code=303)


SECRET_KEY = clave_secreta()
MAX_AGE_COOKIE = int(DURACION_RECORDAR.total_seconds())

app = FastAPI()
# Sesión del login: la SessionMiddleware de Starlette firma la cookie con SECRET_KEY (vía itsdangerous)
# y la marca HttpOnly. SameSite lax, y Secure solo en producción (en desarrollo no hay HTTPS). La
# cookie dura lo máximo (30 días, «Recordarme»); el vencimiento real lo revisa app/web/sesion.py.
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=MAX_AGE_COOKIE,
    same_site="lax",
    https_only=os.environ.get("ENVIRONMENT") == "production",
)
app.add_exception_handler(SinSesion, sin_sesion)

CABECERAS_SEGURIDAD = {
    "X-Content-Type-Options": "nosniff",  # el navegador no adivina tipos (un .txt no corre como JS)
    "X-Frame-Options": "DENY",  # nadie puede meter la app en un iframe para engañar clics
    "Referrer-Policy": "same-origin",  # las URLs (con mes, filtros, búsquedas) no salen a otros sitios
}


@app.middleware("http")
async def seguridad(request: Request, call_next):
    """Cabeceras de seguridad en todo, y la API no acepta cambios pedidos desde otro sitio.

    El navegador manda Origin en las peticiones POST/PUT/DELETE; si no coincide con este host, alguien
    está intentando usar la sesión de la persona desde otra página (CSRF). La cookie ya es SameSite=Lax:
    esto es una segunda barrera. Se compara solo host y puerto, porque detrás de un proxy con HTTPS la
    app puede ver http."""
    origen = request.headers.get("origin")
    if (origen is not None and request.method in ("POST", "PUT", "PATCH", "DELETE")
            and request.url.path.startswith("/api/")
            and urlsplit(origen).netloc != request.headers.get("host", "")):
        respuesta = JSONResponse(status_code=403, content={"detail": "Origen no permitido."})
    else:
        respuesta = await call_next(request)
    respuesta.headers.update(CABECERAS_SEGURIDAD)
    return respuesta
app.mount("/static", Estaticos(directory=Path(__file__).parent / "static"), name="static")
app.include_router(views.router)
app.include_router(api_movimientos.router)
app.include_router(api_categorias.router)
app.include_router(api_cuentas.router)
app.include_router(api_cuentas.router_pagos)
app.include_router(api_ia.router)
app.include_router(api_presupuestos.router)
app.include_router(api_auth.router)


@app.get("/", include_in_schema=False)
def inicio(request: Request):
    """La raíz lleva al Resumen con sesión y al login sin ella."""
    return RedirectResponse("/resumen" if usuario_opcional(request) else "/login", status_code=303)
