"""Ordenar Otros (Categorías): la IA agrupa los movimientos de "Otros" del mes y propone a qué
categoría pasar cada grupo; solo una categoría nueva si agrupa al menos 2 movimientos. Gemini
recibe solo las descripciones (y el tipo); nada cambia hasta que el usuario acepta un grupo."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.categorias import CategoriaEntrada
from app.schemas.movimientos import MovimientoEntrada
from app.services import categorias, ia, movimientos

client = TestClient(app)
URL = "/api/v1/ia/ordenar-otros"
APLICAR = "/api/v1/ia/ordenar-otros/aplicar"
USUARIO = 1
MERCADO, TRANSPORTE, OTROS_GASTOS, OTROS_INGRESOS, SALARIO = 3, 4, 7, 2, 1


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 11, 15))
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


def mov(descripcion, categoria_id=OTROS_GASTOS, tipo="gasto", fecha=date(2026, 11, 10), monto="10000"):
    cuenta = movimientos.catalogo(USUARIO)[0][0].id
    return movimientos.crear(USUARIO, MovimientoEntrada(tipo=tipo, monto=Decimal(monto), categoria_id=categoria_id,
                                                        cuenta_id=cuenta, fecha=fecha, descripcion=descripcion)).id


def gemini(monkeypatch, grupos):
    """Gemini responde estos grupos; devuelve la lista de prompts que recibió."""
    prompts = []

    def falso(prompt):
        prompts.append(prompt)
        return ia._OrdenGemini(grupos=[ia._GrupoGemini(**g) for g in grupos])

    monkeypatch.setattr(ia, "_ordenar_con_gemini", falso)
    return prompts


def pedir(anio=2026, mes=11):
    r = client.get(URL, params={"anio": anio, "mes": mes})
    assert r.status_code == 200, r.text
    return r.json()


def ids(grupo):
    return sorted(m["id"] for m in grupo["movimientos"])


# ---------- Sugerir ----------

def test_agrupa_en_existentes_y_en_una_nueva(monkeypatch):
    pan, huevos, toby, gato = mov("Pan"), mov("Huevos"), mov("Concentrado para Toby"), mov("Arena del gato")
    regalo = mov("Regalo")
    gemini(monkeypatch, [
        {"categoria_id": MERCADO, "movimientos": [pan, huevos]},
        {"categoria_nueva": "Mascotas", "movimientos": [toby, gato]},
    ])

    r = pedir()

    assert r["revisados"] == 5
    mercado, mascotas = r["grupos"]
    assert (mercado["categoria"]["nombre"], mercado["categoria_nueva"], ids(mercado)) == ("Mercado", None, sorted([pan, huevos]))
    assert (mascotas["categoria"], mascotas["categoria_nueva"], mascotas["tipo"]) == (None, "Mascotas", "gasto")
    assert [m["descripcion"] for m in r["quedan"]] == ["Regalo"]
    assert [m["id"] for m in r["quedan"]] == [regalo]


def test_gemini_solo_recibe_descripciones_y_tipo(monkeypatch):
    mov("Concentrado para Toby", monto="61234")
    mov("Freelance diseño", categoria_id=OTROS_INGRESOS, tipo="ingreso")
    mov("Taxi", categoria_id=TRANSPORTE)  # no está en Otros: no se manda
    prompts = gemini(monkeypatch, [])

    pedir()

    prompt = prompts[0]
    assert "Concentrado para Toby" in prompt and "Freelance diseño" in prompt
    assert "Taxi" not in prompt.split("Movimientos")[1]
    assert "61234" not in prompt and "61.234" not in prompt
    assert "2026-11-10" not in prompt
    for cuenta in movimientos.catalogo(USUARIO)[0]:
        assert cuenta.nombre not in prompt


def test_solo_el_mes_pedido(monkeypatch):
    mov("Concentrado", fecha=date(2026, 10, 3))
    prompts = gemini(monkeypatch, [])
    assert pedir()["revisados"] == 0
    assert prompts == []  # nada que revisar: no se llama a Gemini


def test_los_sin_descripcion_no_se_revisan(monkeypatch):
    mov("")
    toby = mov("Concentrado")
    gemini(monkeypatch, [])
    r = pedir()
    assert (r["revisados"], r["sin_descripcion"]) == (1, 1)
    assert [m["id"] for m in r["quedan"]] == [toby]


def test_una_nueva_necesita_al_menos_dos_movimientos(monkeypatch):
    toby = mov("Concentrado para Toby")
    gemini(monkeypatch, [{"categoria_nueva": "Mascotas", "movimientos": [toby]}])
    r = pedir()
    assert r["grupos"] == []
    assert [m["id"] for m in r["quedan"]] == [toby]


def test_una_nueva_que_ya_existe_usa_la_que_hay(monkeypatch):
    propia = categorias.crear(USUARIO, CategoriaEntrada(nombre="Mascota", tipo="gasto"))
    a, b = mov("Concentrado"), mov("Arena")
    gemini(monkeypatch, [{"categoria_nueva": "mascotas", "movimientos": [a, b]}])
    (grupo,) = pedir()["grupos"]
    assert (grupo["categoria"]["id"], grupo["categoria_nueva"]) == (propia.id, None)


def test_dos_grupos_con_la_misma_categoria_se_juntan(monkeypatch):
    a, b, c = mov("Pan"), mov("Huevos"), mov("Leche")
    gemini(monkeypatch, [{"categoria_id": MERCADO, "movimientos": [a]},
                         {"categoria_nueva": "Mercado", "movimientos": [b, c]}])
    (grupo,) = pedir()["grupos"]
    assert ids(grupo) == sorted([a, b, c])


@pytest.mark.parametrize("nombre", ["", "x" * (categorias.MAX_NOMBRE + 1), "Otros varios"])
def test_nombres_nuevos_que_no_sirven_se_descartan(monkeypatch, nombre):
    a, b = mov("Concentrado"), mov("Arena")
    gemini(monkeypatch, [{"categoria_nueva": nombre, "movimientos": [a, b]}])
    r = pedir()
    assert r["grupos"] == [] and len(r["quedan"]) == 2


def test_lo_que_gemini_inventa_o_repite_se_descarta(monkeypatch):
    a, b = mov("Pan"), mov("Huevos")
    taxi = mov("Taxi", categoria_id=TRANSPORTE)  # no estaba en Otros
    salario = mov("Bono", categoria_id=OTROS_INGRESOS, tipo="ingreso")  # ingreso: no va a Mercado
    gemini(monkeypatch, [
        {"categoria_id": MERCADO, "movimientos": [a, a, 99999, taxi, salario]},
        {"categoria_id": TRANSPORTE, "movimientos": [a, b]},  # a ya está en otro grupo
        {"categoria_id": OTROS_GASTOS, "movimientos": []},
    ])
    mercado, transporte = pedir()["grupos"]
    assert ids(mercado) == [a]
    assert ids(transporte) == [b]


def test_no_propone_mover_a_otros_ni_a_una_categoria_del_otro_tipo(monkeypatch):
    a, b = mov("Pan"), mov("Huevos")
    gemini(monkeypatch, [{"categoria_id": OTROS_GASTOS, "movimientos": [a]},
                         {"categoria_id": SALARIO, "movimientos": [b]}])
    r = pedir()
    assert r["grupos"] == [] and len(r["quedan"]) == 2


def test_sin_cupo_no_propone_nuevas(monkeypatch):
    for i in range(categorias.MAX_PROPIAS):
        categorias.crear(USUARIO, CategoriaEntrada(nombre=f"Propia {i}", tipo="gasto"))
    a, b = mov("Concentrado"), mov("Arena")
    gemini(monkeypatch, [{"categoria_nueva": "Mascotas", "movimientos": [a, b]}])
    assert pedir()["grupos"] == []


def test_se_guarda_y_no_gasta_otra_consulta(monkeypatch):
    mov("Concentrado")
    prompts = gemini(monkeypatch, [])
    pedir()
    pedir()
    assert len(prompts) == 1
    mov("Arena")  # cambió lo que hay en Otros: se vuelve a pedir
    pedir()
    assert len(prompts) == 2


def test_mes_no_valido_o_sin_clave(monkeypatch):
    assert client.get(URL, params={"anio": 2026, "mes": 13}).status_code == 422
    assert client.get(URL, params={"anio": 2026, "mes": 12}).status_code == 422  # futuro
    monkeypatch.delenv("GEMINI_API_KEY")
    assert client.get(URL, params={"anio": 2026, "mes": 11}).status_code == 503


# ---------- Aplicar un grupo ----------

def categoria_de(id):
    return movimientos.obtener(USUARIO, id).categoria


def test_aplicar_a_una_existente(monkeypatch):
    a, b, c = mov("Pan"), mov("Huevos"), mov("Leche")
    r = client.post(APLICAR, json={"categoria_id": MERCADO, "movimientos": [a, b]})
    assert r.status_code == 200, r.text
    assert r.json() == {"categoria": {"id": MERCADO, "nombre": "Mercado", "tipo": "gasto"}, "movidos": 2}
    assert categoria_de(a).id == categoria_de(b).id == MERCADO
    assert categoria_de(c).id == OTROS_GASTOS  # desmarcado: se queda en Otros


def test_aplicar_crea_la_nueva(monkeypatch):
    a, b = mov("Concentrado"), mov("Arena")
    r = client.post(APLICAR, json={"categoria_nueva": "Mascotas", "movimientos": [a, b]})
    assert r.status_code == 200, r.text
    nueva = r.json()["categoria"]
    assert nueva["nombre"] == "Mascotas" and nueva["tipo"] == "gasto"
    assert categoria_de(a).id == categoria_de(b).id == nueva["id"]


def test_aplicar_conserva_el_resto_del_movimiento(monkeypatch):
    a = mov("Concentrado", monto="61234.5", fecha=date(2026, 11, 3))
    antes = movimientos.obtener(USUARIO, a)
    client.post(APLICAR, json={"categoria_id": MERCADO, "movimientos": [a]})
    despues = movimientos.obtener(USUARIO, a)
    assert despues.model_dump(exclude={"categoria"}) == antes.model_dump(exclude={"categoria"})


@pytest.mark.parametrize("cuerpo", [
    {"categoria_id": MERCADO, "movimientos": []},
    {"categoria_id": MERCADO},
    {"movimientos": [1]},
    {"categoria_id": MERCADO, "categoria_nueva": "X", "movimientos": [1]},
    {"categoria_id": OTROS_GASTOS, "movimientos": [1]},
    {"categoria_id": SALARIO, "movimientos": [1]},  # de ingresos
    {"categoria_id": 999, "movimientos": [1]},
    "nada",
])
def test_aplicar_rechaza_lo_que_no_es_valido(monkeypatch, cuerpo):
    pan = mov("Pan")
    if isinstance(cuerpo, dict) and cuerpo.get("movimientos") == [1]:
        cuerpo = cuerpo | {"movimientos": [pan]}  # el 1 de la tabla es "Pan"
    r = client.post(APLICAR, json=cuerpo)
    assert r.status_code == 422
    assert categoria_de(pan).id == OTROS_GASTOS


def test_aplicar_solo_mueve_movimientos_que_siguen_en_otros(monkeypatch):
    a = mov("Pan")
    taxi = mov("Taxi", categoria_id=TRANSPORTE)
    r = client.post(APLICAR, json={"categoria_id": MERCADO, "movimientos": [a, taxi]})
    assert r.status_code == 422
    assert categoria_de(a).id == OTROS_GASTOS and categoria_de(taxi).id == TRANSPORTE  # nada a medias


def test_aplicar_una_nueva_con_nombre_repetido_no_mueve_nada(monkeypatch):
    categorias.crear(USUARIO, CategoriaEntrada(nombre="Mascotas", tipo="gasto"))
    a = mov("Concentrado")
    r = client.post(APLICAR, json={"categoria_nueva": "Mascotas", "movimientos": [a]})
    assert r.status_code == 422 and "nombre" in r.json()["errores"]
    assert categoria_de(a).id == OTROS_GASTOS


def test_aplicar_no_gasta_consultas_de_ia(monkeypatch):
    a = mov("Pan")
    monkeypatch.setattr(ia, "_ordenar_con_gemini", lambda p: pytest.fail("no debe llamar a Gemini"))
    assert client.post(APLICAR, json={"categoria_id": MERCADO, "movimientos": [a]}).status_code == 200


# ---------- Página ----------

def test_categorias_tiene_su_menu_de_ia_solo_con_clave(monkeypatch):
    html = client.get("/categorias").text
    assert "data-ordenar-otros " in html and "js/ordenar-otros.js" in html
    assert "data-asistente " not in html and "data-analisis " not in html
    monkeypatch.delenv("GEMINI_API_KEY")
    assert "data-ordenar-otros " not in client.get("/categorias").text
