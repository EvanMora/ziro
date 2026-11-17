"""Los límites de intentos (login, registro) y de consultas a la IA viven en la tabla `intentos`: en
Vercel hay varias instancias de la app y, si cada una contara por su lado en memoria, el límite real
sería el de una multiplicado por las que haya (y se reiniciaría con cada instancia nueva)."""
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.services import database, ia, limites
from app.services.limites import LimiteIntentos

pytestmark = pytest.mark.sin_plantilla


def _filas(prefijo: str = "") -> int:
    with database.sesion() as db:
        return db.execute(text("SELECT COUNT(*) FROM intentos WHERE clave LIKE :p"), {"p": prefijo + "%"}).scalar_one()


def test_dos_instancias_comparten_el_limite():
    una = LimiteIntentos("login", 5, timedelta(minutes=15))
    otra = LimiteIntentos("login", 5, timedelta(minutes=15))
    for _ in range(4):
        una.registrar("ip:1.2.3.4")
    assert otra.bloqueado("ip:1.2.3.4") is False

    una.registrar("ip:1.2.3.4")
    assert otra.bloqueado("ip:1.2.3.4") is True
    assert otra.bloqueado("ip:9.9.9.9") is False


def test_limites_de_distinto_nombre_no_se_mezclan():
    for _ in range(5):
        limites.LOGIN.registrar("ip:1.2.3.4")

    assert limites.LOGIN.bloqueado("ip:1.2.3.4") is True
    assert limites.REGISTRO.bloqueado("ip:1.2.3.4") is False


def test_la_ventana_vence(monkeypatch):
    for _ in range(5):
        limites.LOGIN.registrar("ip:1.2.3.4")
    real = limites.ahora()

    monkeypatch.setattr(limites, "ahora", lambda: real + timedelta(minutes=14, seconds=59))
    assert limites.LOGIN.bloqueado("ip:1.2.3.4") is True
    monkeypatch.setattr(limites, "ahora", lambda: real + timedelta(minutes=15, seconds=1))
    assert limites.LOGIN.bloqueado("ip:1.2.3.4") is False


def test_limpiar_y_reiniciar():
    for _ in range(5):
        limites.LOGIN.registrar("correo:ana@x.com")
        limites.LOGIN.registrar("ip:1.2.3.4")
        limites.REGISTRO.registrar("ip:1.2.3.4")

    limites.LOGIN.limpiar("correo:ana@x.com")
    assert limites.LOGIN.bloqueado("correo:ana@x.com") is False
    assert limites.LOGIN.bloqueado("ip:1.2.3.4") is True

    limites.LOGIN.reiniciar()
    assert limites.LOGIN.bloqueado("ip:1.2.3.4") is False
    assert limites.REGISTRO.bloqueado("ip:1.2.3.4") is True


def test_registrar_borra_lo_viejo(monkeypatch):
    for _ in range(3):
        limites.LOGIN.registrar("ip:1.2.3.4")
    limites.LOGIN.registrar("ip:5.5.5.5")
    real = limites.ahora()
    monkeypatch.setattr(limites, "ahora", lambda: real + timedelta(days=2))

    limites.LOGIN.registrar("ip:1.2.3.4")

    # De esa clave solo queda el intento nuevo; lo de otras claves no se toca.
    assert _filas("login:ip:1.2.3.4") == 1
    assert _filas("login:ip:5.5.5.5") == 1


def test_clave_larga_cabe_en_la_columna():
    # El correo del login no tiene tope de largo: la clave no puede desbordar la columna (Postgres
    # respondería con un error en vez de contar el intento).
    enorme = "correo:" + "a" * 5000 + "@x.com"
    for _ in range(5):
        limites.LOGIN.registrar(enorme)

    assert limites.LOGIN.bloqueado(enorme) is True
    assert limites.LOGIN.bloqueado("correo:" + "a" * 4999 + "@x.com") is False
    with database.sesion() as db:
        assert db.execute(text("SELECT MAX(LENGTH(clave)) FROM intentos")).scalar_one() <= 200


# ---------- IA ----------

def test_ia_comparte_el_limite_entre_instancias(monkeypatch):
    monkeypatch.setattr(ia, "_reloj", lambda: 1_800_000_000.0)
    for _ in range(ia.LIMITE_POR_MINUTO):
        ia._registrar_consulta(7)

    # Nada del conteo vive en la memoria del proceso: otra instancia ve las mismas consultas.
    assert not hasattr(ia, "_consultas")
    assert ia.consultas_registradas(7) == ia.LIMITE_POR_MINUTO
    with pytest.raises(ia.LimiteExcedido):
        ia._registrar_consulta(7)
    ia._registrar_consulta(8)  # el límite es por usuario


def test_ia_reiniciar_limite_no_toca_el_login(monkeypatch):
    monkeypatch.setattr(ia, "_reloj", lambda: 1_800_000_000.0)
    ia._registrar_consulta(7)
    limites.LOGIN.registrar("ip:1.2.3.4")

    ia.reiniciar_limite()

    assert ia.consultas_registradas(7) == 0
    assert _filas("login:") == 1
