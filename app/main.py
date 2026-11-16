import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth as api_auth
from app.api import categorias as api_categorias
from app.api import cuentas as api_cuentas
from app.api import ia as api_ia
from app.api import movimientos as api_movimientos
from app.api import presupuestos as api_presupuestos
from app.web import views

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


app = FastAPI()
# Sesión del login: la SessionMiddleware de Starlette firma la cookie con SECRET_KEY (via itsdangerous).
# Mismo Site lax y secure solo en producción; en desarrollo (http://localhost) no se exige HTTPS.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SECRET_KEY") or "desarrollo-inseguro-cambiar",
    same_site="lax",
    https_only=os.environ.get("ENVIRONMENT") == "production",
)
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
def inicio():
    """La raíz lleva al Resumen. TODO(backend): con el login real, a /login si no hay sesión."""
    return RedirectResponse("/resumen")
