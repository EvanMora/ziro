"""API de inicio de sesión con Google (OAuth / Authlib).

No se hacen llamadas reales a Google: se simula el cliente OAuth devuelto por
`app.services.google_oauth.cliente()` para comprobar el comportamiento de las
rutas: creación de usuario, vinculación al correo, redirección y manejo de errores.
"""
from fastapi.responses import RedirectResponse
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import google_oauth, usuarios
from authlib.integrations.base_client import OAuthError

client = TestClient(app, follow_redirects=False)


@pytest.fixture(autouse=True)
def _almacen_limpio():
    usuarios.reiniciar()
    yield
    usuarios.reiniciar()


class GoogleClienteMock:
    """Simula el cliente OAuth de Authlib."""

    def __init__(self, userinfo=None, token=None, token_error=None):
        self._info = userinfo or _info_google()
        self.token = token or {"access_token": "tok123", "id_token": "dummy"}
        self.token_error = token_error
        self.redirect_uri = None

    async def authorize_redirect(self, request, redirect_uri=None, **kwargs):
        self.redirect_uri = redirect_uri
        return RedirectResponse(
            f"https://accounts.google.com/o/oauth2/v2/auth?redirect_uri={redirect_uri}",
            status_code=302,
        )

    async def authorize_access_token(self, request, **kwargs):
        if self.token_error:
            raise OAuthError(error="access_denied", description="el usuario canceló")
        return self.token

    async def userinfo(self, token=None, **kwargs):
        return self._info


def _info_google(**overrides) -> dict:
    base = {
        "sub": "google-sub-abc123",
        "email": "evan@ziro.com",
        "email_verified": True,
        "name": "Evan Google",
        "picture": "https://example.com/foto.jpg",
    }
    return {**base, **overrides}


def test_google_button_appears_on_login_page_when_configured(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")

    r = client.get("/login")

    assert r.status_code == 200
    assert 'href="/auth/google/login"' in r.text
    assert "Continuar con Google" in r.text


def test_google_button_is_hidden_when_not_configured(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

    r = client.get("/login")

    assert r.status_code == 200
    assert "Continuar con Google" not in r.text


def test_login_redirects_to_google_authorization_page(monkeypatch):
    mock = GoogleClienteMock()
    monkeypatch.setattr(google_oauth, "cliente", lambda: mock)

    r = client.get("/auth/google/login")

    assert r.status_code == 302
    assert r.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert mock.redirect_uri == "http://testserver/auth/google/callback"


def test_login_redirects_to_login_page_when_not_configured(monkeypatch):
    monkeypatch.setattr(google_oauth, "cliente", lambda: None)

    r = client.get("/auth/google/login")

    assert r.status_code == 302
    assert r.headers["location"] == "/login?error=google_no_configurado"


def test_callback_creates_google_user_and_opens_session(monkeypatch):
    mock = GoogleClienteMock(token={"access_token": "tok"})
    monkeypatch.setattr(google_oauth, "cliente", lambda: mock)

    r = client.get("/auth/google/callback?code=fake&state=abc")

    assert r.status_code == 302
    assert r.headers["location"] == "/resumen"
    assert "session=" in r.headers["set-cookie"]

    usuario = usuarios.buscar_por_email("evan@ziro.com")
    assert usuario is not None
    assert usuario.google_sub == "google-sub-abc123"
    assert usuario.foto_url == "https://example.com/foto.jpg"
    assert usuario.nombre == "Evan Google"
    assert usuario.password_hash is None


def test_callback_links_google_to_existing_password_user(monkeypatch):
    usuarios.crear(email="evan@ziro.com", password="secreta123", nombre="Evan Pro")
    mock = GoogleClienteMock(token={"access_token": "tok"})
    monkeypatch.setattr(google_oauth, "cliente", lambda: mock)

    r = client.get("/auth/google/callback?code=fake&state=abc")

    assert r.status_code == 302
    assert r.headers["location"] == "/resumen"

    # El mismo usuario (id 1) queda vinculado a Google; no se crea otro.
    usuario = usuarios.obtener(1)
    assert usuario.google_sub == "google-sub-abc123"
    assert usuario.password_hash is not None
    assert usuarios.obtener(2) is None


def test_callback_uses_existing_google_user_without_duplication(monkeypatch):
    usuarios.buscar_o_vincular_con_google(
        google_sub="google-sub-abc123",
        nombre="Evan Google",
        email="evan@ziro.com",
        foto_url="https://example.com/foto.jpg",
    )
    mock = GoogleClienteMock(token={"access_token": "tok"})
    monkeypatch.setattr(google_oauth, "cliente", lambda: mock)

    r = client.get("/auth/google/callback?code=fake&state=abc")

    assert r.status_code == 302
    assert r.headers["location"] == "/resumen"
    assert usuarios.obtener(1) is not None
    assert usuarios.obtener(2) is None


def test_callback_uses_userinfo_from_token_when_present(monkeypatch):
    mock = GoogleClienteMock(
        userinfo={
            "sub": "google-sub-from-token",
            "email": "token@ziro.com",
            "email_verified": True,
            "name": "Token User",
        }
    )
    mock.token = {"access_token": "tok", "userinfo": mock._info}
    monkeypatch.setattr(google_oauth, "cliente", lambda: mock)

    r = client.get("/auth/google/callback?code=fake&state=abc")

    assert r.status_code == 302
    assert r.headers["location"] == "/resumen"
    usuario = usuarios.buscar_por_email("token@ziro.com")
    assert usuario.google_sub == "google-sub-from-token"


def test_callback_with_unverified_email_does_not_create_user(monkeypatch):
    mock = GoogleClienteMock()
    mock._info = _info_google(email_verified=False)
    monkeypatch.setattr(google_oauth, "cliente", lambda: mock)

    r = client.get("/auth/google/callback?code=fake&state=abc")

    assert r.headers["location"] == "/login?error=google"
    assert usuarios.buscar_por_email("evan@ziro.com") is None


def test_callback_with_google_error_redirects_to_login(monkeypatch):
    mock = GoogleClienteMock(token_error=True)
    monkeypatch.setattr(google_oauth, "cliente", lambda: mock)

    r = client.get("/auth/google/callback?code=fake&state=abc&error=access_denied")

    assert r.headers["location"] == "/login?error=google"
    assert usuarios.buscar_por_email("evan@ziro.com") is None


def test_callback_without_client_configured_redirects_to_login(monkeypatch):
    monkeypatch.setattr(google_oauth, "cliente", lambda: None)

    r = client.get("/auth/google/callback?code=fake&state=abc")

    assert r.headers["location"] == "/login?error=google_no_configurado"
