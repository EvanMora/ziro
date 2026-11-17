"""Auth: registro, inicio y cierre de sesión. El inicio con Google (Authlib) es la otra rama de este
router: /auth/google/login y /auth/google/callback, que guardan el id en la misma sesión."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.schemas.auth import LoginEntrada, RegistroEntrada
from app.services import usuarios, google_oauth
from app.services.comun import ErrorValidacion

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Inicio de sesión con Google: son redirecciones (302) para el navegador, así que van en el mismo
# router aunque la rama no sea JSON (el id del Google entra en la misma sesión que el resto).
router_google = APIRouter(prefix="/auth/google", tags=["auth"])


@router_google.get("/login", name="google_login")
async def login_google(request: Request):
    """Redirige al consentimiento de Google (Authlib). Si no hay credenciales configuradas, va a /login."""
    cliente = google_oauth.cliente()
    if cliente is None:
        return RedirectResponse("/login?error=google_no_configurado", status_code=302)
    redirect_uri = request.url_for("google_callback")
    return await cliente.authorize_redirect(request, redirect_uri)


@router_google.get("/callback", name="google_callback")
async def callback_google(request: Request):
    """Recibe el code de Google, lo canjea por el access token, lee el usuario y abre la sesión."""
    cliente = google_oauth.cliente()
    if cliente is None:
        return RedirectResponse("/login?error=google_no_configurado", status_code=302)
    try:
        token = await cliente.authorize_access_token(request)
        userinfo = token.get("userinfo") if token else None
        if not userinfo:
            userinfo = await cliente.userinfo(token=token) if token else None
        email = (userinfo or {}).get("email") or ""
        email = (email or "").strip().lower()
        verificado = (userinfo or {}).get("email_verified")
        if isinstance(verificado, str):
            verificado = verificado.lower() == "true"
        if not email or not userinfo.get("sub") or not verificado:
            # Sin id o sin correo verificado no hay login (p. ej. el correo no está en los
            # usuarios de prueba de Google o el permiso fue denegado).
            return RedirectResponse("/login?error=google", status_code=302)
        usuario = usuarios.buscar_o_vincular_con_google(
            google_sub=str(userinfo["sub"]),
            nombre=(userinfo.get("name") or "").strip(),
            email=email,
            foto_url=userinfo.get("picture") or None,
        )
    except Exception:
        # El usuario canceló o Google falló: no se abre sesión.
        return RedirectResponse("/login?error=google", status_code=302)
    request.session["usuario_id"] = usuario.id
    return RedirectResponse("/resumen", status_code=302)


@router.post("/registro")
def registrar(payload: RegistroEntrada, request: Request) -> JSONResponse:
    """Crea el usuario en la base de datos (alta con registro) y abre su sesión."""
    try:
        usuario = usuarios.crear(nombre=payload.nombre, email=payload.email, password=payload.password)
    except ErrorValidacion as error:
        # El correo ya está registrado: el error llega por campo para que el formulario lo muestre
        # en el campo del email.
        return JSONResponse(status_code=422, content={"errores": error.errores})
    request.session["usuario_id"] = usuario.id
    return JSONResponse(status_code=201, content=usuarios.a_sesion(usuario).model_dump(mode="json"))


@router.post("/login")
def login(payload: LoginEntrada, request: Request) -> JSONResponse:
    """Valida el correo y la contraseña; si son buenos, guarda el usuario en la sesión (cookie)."""
    usuario = usuarios.verificar(payload.email, payload.password)
    if usuario is None:
        # Mismo mensaje si falla el correo o la contraseña: no se dice cuál.
        return JSONResponse(status_code=401, content={"detail": "Correo o contraseña incorrectos."})
    request.session["usuario_id"] = usuario.id
    return JSONResponse(status_code=200, content=usuarios.a_sesion(usuario).model_dump(mode="json"))


@router.post("/logout")
def logout(request: Request) -> JSONResponse:
    """Borra la sesión y cierra el login."""
    request.session.clear()
    return JSONResponse(status_code=200, content={"detail": "Sesión cerrada."})
