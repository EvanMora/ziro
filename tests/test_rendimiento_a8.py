"""Auditoría de rendimiento, hallazgo A8: orquestación de /resumen (ver docs/auditorias/2026-11-03-rendimiento.md).

Que el Resumen lea cada cosa una sola vez por petición, que el global static() de Jinja dé las mismas
rutas que url_for y que quitar el espacio en blanco de los {% ... %} no pegue palabras."""
import os
import re
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.cuentas import CuentaEntrada, PagoEntrada
from app.services import categorias, cuentas, movimientos, presupuestos
from app.services.dashboard import obtener_resumen
from app.web import views

client = TestClient(app)
U = 1


@pytest.fixture(autouse=True)
def _hoy_fijo(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 11, 15))


# ---------- Plantillas ----------

@pytest.mark.parametrize("path", ["css/app.css", "img/favicon.svg", "js/app-shell.js", "fonts/inter-latin.woff2"])
def test_static_da_la_misma_ruta_que_url_for(path):
    # Si cambia el app.mount("/static", ...) de app/main.py, este test avisa que static() quedó viejo.
    assert views.static(path) == app.url_path_for("static", path=path)
    assert client.get(views.static(path)).status_code == 200


def test_static_esta_en_las_plantillas():
    assert views.templates.env.from_string("{{ static('css/app.css') }}").render() == "/static/css/app.css"


def test_entorno_de_jinja():
    env = views.templates.env
    assert env.trim_blocks and env.lstrip_blocks
    # Solo con "fastapi dev" (FASTAPI_ENV=development) se revisa en cada petición si cambió una plantilla.
    assert env.auto_reload is (os.environ.get("FASTAPI_ENV") == "development")


@pytest.mark.parametrize("ruta", ["/login", "/resumen", "/resumen?anio=2026&mes=10", "/movimientos",
                                  "/cuentas", "/categorias", "/presupuestos", "/presupuestos/nuevo"])
def test_cada_archivo_estatico_enlazado_existe(ruta):
    html = client.get(ruta).text
    enlazados = set(re.findall(r'(?:href|src)="(?:http://testserver)?(/static/[^"]+)"', html))
    assert enlazados
    for url in enlazados:
        assert client.get(url).status_code == 200, url


def _texto(html: str, clase: str) -> str:
    """El texto de la primera etiqueta con esa clase, sin etiquetas y con los espacios colapsados."""
    trozo = html.split(f'class="{clase}"', 1)[1].split(">", 1)[1]
    trozo = re.split(r"</(?:p|a)>", trozo, maxsplit=1)[0]
    return " ".join(re.sub(r"<[^>]+>", "", trozo).split())


def test_los_if_en_linea_no_pegan_palabras():
    html = client.get("/resumen?anio=2026&mes=10").text

    assert re.fullmatch(r"Te quedan \$[\d.]+ de lo que entró este mes\.", _texto(html, "stage__note"))
    assert re.fullmatch(r"Debes \$[\d.]+ en tarjetas · Ver cuentas", _texto(html, "link-row"))


# ---------- Datos del Resumen ----------

def test_los_saldos_del_resumen_son_los_de_cuentas():
    """obtener_resumen ya no usa panel() (que cuenta los usos de cada cuenta), pero da las mismas cifras."""
    cuentas.crear(U, CuentaEntrada(nombre="Visa", tipo="tarjeta", icono="tarjeta", tono="azul",
                                   saldo=Decimal("50000"), cupo=Decimal("900000"), dia_pago=2))
    cuentas.registrar_pago(U, 4, PagoEntrada(monto=Decimal("40000"), cuenta_origen_id=2, fecha=date(2026, 11, 10)))

    r = obtener_resumen(U, 2026, 10)
    panel = cuentas.panel(U)

    assert r.saldo_total == panel.tienes
    assert r.deuda_tarjetas == panel.debes == Decimal("850000")
    assert [(c.nombre, c.saldo) for c in r.cuentas] == [(c.cuenta.nombre, c.saldo) for c in panel.dinero]


def test_pasar_lo_ya_leido_no_cambia_el_resultado():
    lista = movimientos.listar(U, 2026, 10)
    gastos = presupuestos.gastos_del_mes(U, 2026, 10, lista=lista)

    assert obtener_resumen(U, 2026, 10, lista=lista, lista_cuentas=cuentas.listar(U)) == obtener_resumen(U, 2026, 10)
    assert gastos == presupuestos.gastos_del_mes(U, 2026, 10)
    assert (presupuestos.del_mes(U, 2026, 10, gastos=gastos, lista_categorias=categorias.listar(U))
            == presupuestos.del_mes(U, 2026, 10))


def test_el_resumen_lee_cada_cosa_una_vez(monkeypatch):
    client.get("/resumen?anio=2026&mes=10")  # siembra los meses y crea las cuentas demo
    llamadas: dict[str, int] = {}

    def contar(modulo, nombre):
        original = getattr(modulo, nombre)
        clave = f"{modulo.__name__.rsplit('.', 1)[-1]}.{nombre}"

        def envoltura(*args, **kwargs):
            llamadas[clave] = llamadas.get(clave, 0) + 1
            return original(*args, **kwargs)
        monkeypatch.setattr(modulo, nombre, envoltura)

    contar(movimientos, "listar")
    contar(movimientos, "usos_por_cuenta")
    contar(cuentas, "listar")
    contar(categorias, "listar")
    contar(movimientos, "hoy")

    assert client.get("/resumen?anio=2026&mes=10").status_code == 200

    assert llamadas["movimientos.listar"] == 1  # antes 2: el Resumen y el presupuesto listaban el mes
    assert llamadas["cuentas.listar"] == 1  # antes 3
    assert llamadas["categorias.listar"] == 1  # antes 2
    assert "movimientos.usos_por_cuenta" not in llamadas  # el Resumen no muestra los usos de cada cuenta
    # Una en la ruta y otra en movimientos.desde (los saldos), que no es de esta capa. Antes, 6.
    assert llamadas["movimientos.hoy"] <= 2
