"""Asistente con Gemini. Gemini se reemplaza por respuestas fijas: los tests nunca llaman a la API."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import ia
from app.services import movimientos

client = TestClient(app)
URL = "/api/v1/ia/interpretar-movimiento"


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 11, 15))
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


def gemini_responde(monkeypatch, **campos):
    """Hace que Gemini devuelva esta respuesta y guarda el prompt que recibió."""
    respuesta = {"tipo": "gasto", "monto": 45000, "categoria_id": 4, "cuenta_id": 3,
                 "fecha": "2026-11-14", "descripcion": "Taxi"} | campos
    prompts = []

    def falso(prompt):
        prompts.append(prompt)
        return ia._RespuestaGemini(**respuesta)

    monkeypatch.setattr(ia, "_llamar_gemini", falso)
    return prompts


def test_frase_completa_devuelve_la_sugerencia(monkeypatch):
    prompts = gemini_responde(monkeypatch)

    r = client.post(URL, json={"texto": "ayer gasté 45.000 en taxi en efectivo"})

    assert r.status_code == 200
    assert r.json() == {"tipo": "gasto", "monto": "45000", "categoria_id": 4, "cuenta_id": 3,
                        "fecha": "2026-11-14", "descripcion": "Taxi", "categoria_nueva": None}
    # Gemini recibe la fecha de hoy, el catálogo y la frase.
    assert "domingo 2026-11-15" in prompts[0]
    assert "- 4: Transporte, gasto" in prompts[0] and "- 3: Efectivo" in prompts[0]
    assert prompts[0].endswith("ayer gasté 45.000 en taxi en efectivo")


@pytest.mark.parametrize(
    ("campos", "esperado"),
    [
        ({"monto": 0}, {"monto": None}),
        ({"monto": -500}, {"monto": None}),
        ({"monto": 10**13}, {"monto": None}),
        ({"categoria_id": 99}, {"categoria_id": None}),
        ({"categoria_id": 1}, {"categoria_id": None}),  # Salario es de ingresos, no de gastos
        ({"cuenta_id": 99}, {"cuenta_id": None}),
        ({"fecha": "2026-12-01"}, {"fecha": None}),  # futura
        ({"fecha": "ayer"}, {"fecha": None}),
        ({"fecha": None}, {"fecha": None}),
        ({"descripcion": "  Taxi   al\naeropuerto "}, {"descripcion": "Taxi al aeropuerto"}),
        ({"descripcion": "x" * 200}, {"descripcion": "x" * 80}),
    ],
)
def test_lo_que_no_es_valido_se_descarta(monkeypatch, campos, esperado):
    gemini_responde(monkeypatch, **campos)

    sugerido = client.post(URL, json={"texto": "taxi"}).json()

    for campo, valor in esperado.items():
        assert sugerido[campo] == valor


def test_ingreso(monkeypatch):
    gemini_responde(monkeypatch, tipo="ingreso", monto=3200000, categoria_id=1, cuenta_id=1,
                    descripcion="Salario")

    sugerido = client.post(URL, json={"texto": "me pagaron el sueldo"}).json()

    assert sugerido["tipo"] == "ingreso" and sugerido["categoria_id"] == 1 and sugerido["monto"] == "3200000"


@pytest.mark.parametrize("cuerpo", [{}, {"texto": ""}, {"texto": "   "}, {"texto": 5}, [1, 2], None])
def test_texto_vacio_o_invalido(monkeypatch, cuerpo):
    gemini_responde(monkeypatch)

    r = client.post(URL, json=cuerpo)

    assert r.status_code == 422
    assert r.json()["errores"]["texto"] == "Escribe qué gastaste o recibiste."


def test_texto_demasiado_largo(monkeypatch):
    gemini_responde(monkeypatch)

    r = client.post(URL, json={"texto": "a" * 301})

    assert r.status_code == 422
    assert r.json()["errores"]["texto"] == "Máximo 300 caracteres."


def test_sin_clave_responde_503_sin_llamar_a_gemini(monkeypatch):
    prompts = gemini_responde(monkeypatch)
    monkeypatch.delenv("GEMINI_API_KEY")

    r = client.post(URL, json={"texto": "taxi"})

    assert r.status_code == 503
    assert r.json()["errores"]["general"] == "El asistente no está configurado."
    assert prompts == []


def test_si_gemini_falla_responde_503(monkeypatch):
    def falla(prompt):
        raise ia.ErrorIA("El asistente no respondió. Llena el formulario o inténtalo de nuevo.")

    monkeypatch.setattr(ia, "_llamar_gemini", falla)

    r = client.post(URL, json={"texto": "taxi"})

    assert r.status_code == 503
    assert "no respondió" in r.json()["errores"]["general"]


def test_errores_del_sdk_se_convierten_en_error_ia(monkeypatch):
    class ClienteRoto:
        class models:
            @staticmethod
            def generate_content(**_):
                raise ConnectionError("sin red")

    monkeypatch.setattr(ia, "_cliente", lambda api_key: ClienteRoto)

    with pytest.raises(ia.ErrorIA):
        ia._llamar_gemini("taxi")


def test_el_asistente_aparece_en_el_dialogo_solo_con_clave(monkeypatch):
    assert "data-ia-texto" in client.get("/resumen").text

    monkeypatch.delenv("GEMINI_API_KEY")
    assert "data-ia-texto" not in client.get("/resumen").text


def test_cada_seccion_tiene_su_menu_de_ia_solo_con_clave(monkeypatch):
    movimientos_html = client.get("/movimientos").text
    resumen_html = client.get("/resumen").text
    # Registrar con una frase va en Movimientos; el análisis del mes, en el Resumen.
    assert "data-asistente " in movimientos_html and "js/asistente.js" in movimientos_html
    assert "data-analisis " not in movimientos_html
    assert "data-analisis " in resumen_html and "js/analisis.js" in resumen_html
    assert "data-asistente " not in resumen_html
    # Cuentas no tiene IA.
    cuentas_html = client.get("/cuentas").text
    assert "data-asistente " not in cuentas_html and "data-analisis " not in cuentas_html

    monkeypatch.delenv("GEMINI_API_KEY")
    assert "data-asistente " not in client.get("/movimientos").text
    assert "data-analisis " not in client.get("/resumen").text


# ---------- Límite de consultas por usuario ----------

@pytest.fixture
def reloj(monkeypatch):
    """Reloj falso: los tests avanzan el tiempo sin esperar."""
    ahora = [1000.0]
    monkeypatch.setattr(ia, "_reloj", lambda: ahora[0])
    return ahora


def test_pasado_el_limite_por_minuto_responde_429_sin_llamar_a_gemini(monkeypatch, reloj):
    prompts = gemini_responde(monkeypatch)
    for _ in range(ia.LIMITE_POR_MINUTO):
        assert client.post(URL, json={"texto": "taxi"}).status_code == 200
        reloj[0] += 1

    r = client.post(URL, json={"texto": "taxi"})

    assert r.status_code == 429
    # La primera consulta fue hace 10 s: falta 50 s para que salga de la ventana de un minuto.
    assert r.headers["Retry-After"] == "50"
    assert r.json()["errores"]["general"] == "Hiciste muchas consultas seguidas. Espera 50 s e inténtalo de nuevo."
    assert len(prompts) == ia.LIMITE_POR_MINUTO


def test_al_pasar_el_minuto_se_puede_volver_a_consultar(monkeypatch, reloj):
    gemini_responde(monkeypatch)
    for _ in range(ia.LIMITE_POR_MINUTO):
        client.post(URL, json={"texto": "taxi"})
    assert client.post(URL, json={"texto": "taxi"}).status_code == 429

    reloj[0] += 60

    assert client.post(URL, json={"texto": "taxi"}).status_code == 200


def test_limite_por_dia(monkeypatch, reloj):
    gemini_responde(monkeypatch)
    for _ in range(ia.LIMITE_POR_DIA):
        assert client.post(URL, json={"texto": "taxi"}).status_code == 200
        reloj[0] += 61  # nunca choca con el límite por minuto

    r = client.post(URL, json={"texto": "taxi"})

    assert r.status_code == 429
    assert "por hoy" in r.json()["errores"]["general"]

    reloj[0] += 24 * 60 * 60
    assert client.post(URL, json={"texto": "taxi"}).status_code == 200


def test_las_consultas_rechazadas_antes_de_gemini_no_cuentan(monkeypatch, reloj):
    gemini_responde(monkeypatch)
    for _ in range(ia.LIMITE_POR_MINUTO + 5):
        client.post(URL, json={"texto": ""})  # 422: ni siquiera llega al servicio

    assert client.post(URL, json={"texto": "taxi"}).status_code == 200


def test_el_limite_es_por_usuario(monkeypatch, reloj):
    gemini_responde(monkeypatch)
    for _ in range(ia.LIMITE_POR_MINUTO):
        ia.interpretar(1, "taxi")

    with pytest.raises(ia.LimiteExcedido):
        ia.interpretar(1, "taxi")
    assert ia.interpretar(2, "taxi").monto == 45000


# ---------- Análisis del mes (Resumen) ----------

URL_ANALISIS = "/api/v1/ia/analisis-mes"


def gemini_analiza(monkeypatch, observaciones=None, consejo="Revisa tus gastos de Ocio."):
    """Hace que Gemini devuelva este análisis y guarda las cifras que recibió."""
    prompts = []

    def falso(prompt):
        prompts.append(prompt)
        return ia._AnalisisGemini(observaciones=observaciones or ["El arriendo fue tu mayor gasto."],
                                  consejo=consejo)

    monkeypatch.setattr(ia, "_analizar_con_gemini", falso)
    return prompts


def test_analisis_del_mes(monkeypatch):
    gemini_analiza(monkeypatch, observaciones=["Gastaste $1.874.300 en octubre.",
                                                "El arriendo fue el 58,7 % del gasto."])

    r = client.get(URL_ANALISIS, params={"anio": 2026, "mes": 10})

    assert r.status_code == 200
    assert r.json() == {"anio": 2026, "mes": 10, "sin_datos": False,
                        "observaciones": ["Gastaste $1.874.300 en octubre.", "El arriendo fue el 58,7 % del gasto."],
                        "consejo": "Revisa tus gastos de Ocio."}


def test_las_cifras_las_calcula_python_y_no_incluyen_datos_privados(monkeypatch):
    prompts = gemini_analiza(monkeypatch)
    # Un gasto extra en octubre para que haya cambio frente a septiembre.
    movimientos.crear(1, movimientos.MovimientoEntrada(tipo="gasto", monto=100000, categoria_id=6, cuenta_id=1,
                                                       fecha=date(2026, 10, 5), descripcion="Concierto secreto"))

    client.get(URL_ANALISIS, params={"anio": 2026, "mes": 10})

    cifras = prompts[0]
    assert "Mes: octubre de 2026." in cifras
    assert "Ingresos: $3.200.000." in cifras
    # Los porcentajes llevan espacio de no separación antes del %, como en la pantalla.
    assert "Gastos: $1.974.300, el 61,7\xa0% de los ingresos." in cifras
    assert "Quedó: $1.225.700." in cifras
    assert "- Ocio: $280.000 (14,2\xa0% del gasto); en septiembre fue $180.000, subió 55,6\xa0%." in cifras
    assert "- Arriendo: $1.100.000 (55,7\xa0% del gasto); igual que en septiembre." in cifras
    assert "Mes anterior (septiembre): ingresos $3.200.000, gastos $1.874.300." in cifras
    # Nada de cuentas, saldos ni descripciones.
    for privado in ("Cuenta de ahorros", "Billetera digital", "Efectivo", "Concierto secreto", "Supermercado"):
        assert privado not in cifras


def test_mes_en_curso_se_marca_como_tal(monkeypatch):
    prompts = gemini_analiza(monkeypatch)

    client.get(URL_ANALISIS, params={"anio": 2026, "mes": 11})

    assert "El mes va en curso: van 15 de 30 días." in prompts[0]


def test_frases_con_cifras_inventadas_se_descartan(monkeypatch):
    gemini_analiza(monkeypatch,
                   observaciones=["Gastaste $1.874.300 en octubre.",          # está en las cifras
                                  "Ahorraste $500.000 más que nunca.",        # inventada
                                  "El arriendo fue el 60 % del gasto."],      # mal redondeada
                   consejo="Intenta bajar el Ocio un 20 %.")                  # inventada

    datos = client.get(URL_ANALISIS, params={"anio": 2026, "mes": 10}).json()

    assert datos["observaciones"] == ["Gastaste $1.874.300 en octubre."]
    assert datos["consejo"] == ""


def test_si_todo_es_inventado_responde_503(monkeypatch):
    gemini_analiza(monkeypatch, observaciones=["Gastaste $9.999 en total."], consejo="Ahorra el 50 %.")

    r = client.get(URL_ANALISIS, params={"anio": 2026, "mes": 10})

    assert r.status_code == 503
    assert "no pudo analizar" in r.json()["errores"]["general"]


def test_mes_sin_movimientos_no_llama_a_gemini(monkeypatch):
    prompts = gemini_analiza(monkeypatch)
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 11, 5))  # aún no hay nada sembrado en noviembre

    datos = client.get(URL_ANALISIS, params={"anio": 2026, "mes": 11}).json()

    assert datos["sin_datos"] is True and datos["observaciones"] == []
    assert prompts == []


def test_el_analisis_se_guarda_y_no_gasta_otra_consulta(monkeypatch):
    prompts = gemini_analiza(monkeypatch)

    primero = client.get(URL_ANALISIS, params={"anio": 2026, "mes": 10}).json()
    segundo = client.get(URL_ANALISIS, params={"anio": 2026, "mes": 10}).json()

    assert primero == segundo and len(prompts) == 1
    assert len(ia._consultas[1]) == 1


def test_si_cambian_los_movimientos_se_vuelve_a_analizar(monkeypatch):
    prompts = gemini_analiza(monkeypatch)
    client.get(URL_ANALISIS, params={"anio": 2026, "mes": 10})
    movimientos.crear(1, movimientos.MovimientoEntrada(tipo="gasto", monto=5000, categoria_id=4, cuenta_id=3,
                                                       fecha=date(2026, 10, 2)))

    client.get(URL_ANALISIS, params={"anio": 2026, "mes": 10})

    assert len(prompts) == 2


@pytest.mark.parametrize("params", [{}, {"anio": 2026}, {"anio": "x", "mes": 1}, {"anio": 2026, "mes": 13},
                                    {"anio": 1999, "mes": 1}, {"anio": 2026, "mes": 12}])
def test_mes_no_valido_o_futuro(monkeypatch, params):
    prompts = gemini_analiza(monkeypatch)

    r = client.get(URL_ANALISIS, params=params)

    assert r.status_code == 422
    assert r.json()["errores"]["general"] == "Mes no válido."
    assert prompts == []


def test_analisis_sin_clave_responde_503(monkeypatch):
    gemini_analiza(monkeypatch)
    monkeypatch.delenv("GEMINI_API_KEY")

    r = client.get(URL_ANALISIS, params={"anio": 2026, "mes": 10})

    assert r.status_code == 503


def test_analisis_respeta_el_limite_de_consultas(monkeypatch, reloj):
    gemini_responde(monkeypatch)
    gemini_analiza(monkeypatch)
    for _ in range(ia.LIMITE_POR_MINUTO):
        client.post(URL, json={"texto": "taxi"})

    r = client.get(URL_ANALISIS, params={"anio": 2026, "mes": 10})

    assert r.status_code == 429


def test_los_estaticos_piden_revalidar():
    r = client.get("/static/css/app.css")

    assert r.headers["cache-control"] == "no-cache"


def test_el_prompt_lleva_nombres_de_cuentas_pero_no_saldos(monkeypatch):
    from decimal import Decimal

    from app.schemas.cuentas import PagoEntrada
    from app.services import cuentas
    cuentas.registrar_pago(1, 4, PagoEntrada(monto=Decimal("300000"), cuenta_origen_id=1, fecha=date(2026, 11, 12)))
    prompts = gemini_responde(monkeypatch, cuenta_id=4)

    r = client.post(URL, json={"texto": "pagué 20.000 con la tarjeta"})

    prompt = prompts[0]
    assert "- 4: Tarjeta de crédito" in prompt and "- 2: Billetera digital" in prompt
    for privado in ["3612400", "3.612.400", "3312400", "840000", "840.000", "540000", "3000000", "300000",
                    "cupo", "saldo", "deuda", "Pago"]:
        assert privado not in prompt, privado
    assert r.json()["cuenta_id"] == 4  # una tarjeta sirve para un gasto (es una compra)
