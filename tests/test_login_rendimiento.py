import re

from fastapi.testclient import TestClient

from app.main import app
from app.web import preview

client = TestClient(app)


def test_build_preview_se_calcula_una_vez():
    assert preview.build_preview() is preview.build_preview()


def test_login_prefetchea_los_css_de_resumen():
    login = client.get("/login").text
    resumen = client.get("/resumen").text
    css_login = set(re.findall(r'rel="stylesheet" href="([^"]+\.css)"', login))
    css_resumen = set(re.findall(r'rel="stylesheet" href="([^"]+\.css)"', resumen))
    prefetch = set(re.findall(r'rel="prefetch" href="([^"]+)"', login))

    assert css_resumen - css_login
    assert prefetch == css_resumen - css_login
    for url in prefetch:
        assert client.get(url).status_code == 200, url
