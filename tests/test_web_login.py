from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_login_page_renders_html():
    response = client.get("/login")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Inicia sesión" in response.text


def test_login_form_is_accessible_and_autofill_friendly():
    html = client.get("/login").text

    assert 'action="/api/v1/auth/login"' in html
    assert '<label class="float-field__label" for="email">Correo electrónico</label>' in html
    assert '<label class="float-field__label" for="password">Contraseña</label>' in html
    assert 'aria-label="Mostrar contraseña"' in html
    assert 'autocomplete="email"' in html
    assert 'autocomplete="current-password"' in html
    assert 'role="alert"' in html


def test_login_static_assets_are_served():
    for path in ("/static/css/tokens.css", "/static/css/styles.css", "/static/css/login.css", "/static/js/login.js", "/static/js/login-preview.js", "/static/js/login-card.js"):
        assert client.get(path).status_code == 200, path


def test_la_raiz_lleva_al_login_sin_sesion():
    # Sin sesión (aquí no hay cookie; la raíz no usa la sesión simulada de los tests). Con sesión va
    # al Resumen: tests/test_proteccion.py.
    r = client.get("/", follow_redirects=False)

    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_preview_numbers_are_consistent():
    from app.web import preview

    data = preview.build_preview()
    expenses = sum(amount for _, amount in preview.EXPENSES_BY_CATEGORY)

    assert data["expenses_text"] == preview.money(-expenses, sign=True)
    assert data["savings"][-1]["current"] and data["savings"][-1]["height"] == 100.0
    assert preview.INCOME - expenses == max(preview.SAVINGS + [preview.INCOME - expenses])
    assert [b["status"] for b in data["budgets"]] == ["ok", "warning", "danger"]
