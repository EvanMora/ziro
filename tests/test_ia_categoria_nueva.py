"""El asistente propone una categoría nueva cuando ninguna encaja.

Gemini elige "Otros" de ese tipo y además sugiere un nombre (categoria_nueva). Python lo revisa
antes de devolverlo: si ya existe una categoría así (sin importar tildes, mayúsculas ni plural) usa
esa; si el nombre no sirve o el usuario ya no puede crear más, no sugiere nada. Nunca crea la
categoría: el diálogo la crea solo si el usuario guarda el movimiento."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.categorias import CategoriaEntrada
from app.services import categorias, ia, movimientos

client = TestClient(app)
URL = "/api/v1/ia/interpretar-movimiento"
USUARIO = 1
OTROS_GASTOS, OTROS_INGRESOS, TRANSPORTE = 7, 2, 4


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 11, 15))
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


def sugerencia(monkeypatch, **campos):
    respuesta = {"tipo": "gasto", "monto": 60000, "categoria_id": OTROS_GASTOS, "cuenta_id": 3,
                 "fecha": "2026-11-14", "descripcion": "Concentrado para Toby",
                 "categoria_nueva": "Mascotas"} | campos
    monkeypatch.setattr(ia, "_llamar_gemini", lambda prompt: ia._RespuestaGemini(**respuesta))
    r = client.post(URL, json={"texto": "ayer 60 mil en concentrado para Toby"})
    assert r.status_code == 200
    return r.json()


def test_si_ninguna_encaja_sugiere_una_nueva_y_deja_otros(monkeypatch):
    s = sugerencia(monkeypatch)
    assert s["categoria_nueva"] == "Mascotas"
    assert s["categoria_id"] == OTROS_GASTOS  # si no la acepta, queda como hoy


def test_tambien_para_ingresos(monkeypatch):
    s = sugerencia(monkeypatch, tipo="ingreso", categoria_id=OTROS_INGRESOS, categoria_nueva="Freelance")
    assert (s["categoria_id"], s["categoria_nueva"]) == (OTROS_INGRESOS, "Freelance")


def test_sin_sugerencia_llega_en_null(monkeypatch):
    assert sugerencia(monkeypatch, categoria_id=TRANSPORTE, categoria_nueva=None)["categoria_nueva"] is None


def test_si_ya_eligio_una_que_encaja_no_sugiere_otra(monkeypatch):
    s = sugerencia(monkeypatch, categoria_id=TRANSPORTE, categoria_nueva="Taxis")
    assert (s["categoria_id"], s["categoria_nueva"]) == (TRANSPORTE, None)


@pytest.mark.parametrize("nombre", ["Transporte", "transportes", "TRANSPORTÉ"])
def test_si_ya_existe_usa_la_que_hay(monkeypatch, nombre):
    s = sugerencia(monkeypatch, categoria_nueva=nombre)
    assert (s["categoria_id"], s["categoria_nueva"]) == (TRANSPORTE, None)


def test_si_ya_existe_una_propia_usa_esa(monkeypatch):
    propia = categorias.crear(USUARIO, CategoriaEntrada(nombre="Mascota", tipo="gasto"))
    s = sugerencia(monkeypatch, categoria_nueva="Mascotas")
    assert (s["categoria_id"], s["categoria_nueva"]) == (propia.id, None)


def test_una_del_otro_tipo_no_cuenta_como_existente(monkeypatch):
    categorias.crear(USUARIO, CategoriaEntrada(nombre="Mascotas", tipo="ingreso"))
    assert sugerencia(monkeypatch)["categoria_nueva"] == "Mascotas"


@pytest.mark.parametrize("nombre", ["", "   ", "x" * (categorias.MAX_NOMBRE + 1), "Otros", "Otros gastos varios"])
def test_un_nombre_que_no_sirve_se_descarta(monkeypatch, nombre):
    s = sugerencia(monkeypatch, categoria_nueva=nombre)
    assert (s["categoria_id"], s["categoria_nueva"]) == (OTROS_GASTOS, None)


def test_el_nombre_llega_limpio(monkeypatch):
    assert sugerencia(monkeypatch, categoria_nueva="  Mascotas \n y  más ")["categoria_nueva"] == "Mascotas y más"


def test_sin_cupo_para_categorias_propias_no_sugiere(monkeypatch):
    for i in range(categorias.MAX_PROPIAS):
        categorias.crear(USUARIO, CategoriaEntrada(nombre=f"Propia {i}", tipo="gasto"))
    assert sugerencia(monkeypatch)["categoria_nueva"] is None


def test_sugerir_no_crea_la_categoria(monkeypatch):
    antes = len(categorias.listar(USUARIO))
    sugerencia(monkeypatch)
    assert len(categorias.listar(USUARIO)) == antes


def test_las_instrucciones_piden_la_sugerencia_solo_si_nada_encaja():
    assert "categoria_nueva" in ia._INSTRUCCIONES
    assert "categoria_nueva" in ia._RespuestaGemini.model_fields


def test_el_dialogo_trae_el_aviso_de_categoria_nueva():
    html = client.get("/movimientos").text
    assert "data-categoria-nueva" in html
    assert "data-categoria-nueva-nombre" in html
