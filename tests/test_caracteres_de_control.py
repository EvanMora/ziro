"""Los caracteres de control (el nulo \\x00 y compañía) no llegan a la base. Postgres rechaza el nulo
en cualquier texto: sin limpiarlo, un nombre o un correo con ese carácter respondería con un error
500 en vez de guardarse limpio o de un «correo o contraseña incorrectos»."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.categorias import CategoriaEntrada
from app.schemas.cuentas import CuentaEntrada
from app.schemas.metas import MetaEntrada
from app.schemas.movimientos import MovimientoEntrada
from app.services import categorias, cuentas, metas, movimientos, usuarios
from app.services.comun import limpiar_texto

pytestmark = pytest.mark.sin_plantilla


@pytest.mark.parametrize(("texto", "limpio"), [
    ("Nu\x00lo", "Nulo"),
    ("\x00", ""),
    ("a\x07b\x1bc\x7f", "abc"),
    ("a\tb\nc", "a b c"),  # los espacios en blanco siguen separando palabras
    ("Mercado  de la 85", "Mercado de la 85"),
])
def test_limpiar_texto_quita_los_caracteres_de_control(texto, limpio):
    assert limpiar_texto(texto) == limpio


def test_el_registro_guarda_el_nombre_sin_caracteres_de_control():
    usuario = usuarios.crear("ana@x.com", "secreta123", "  Ana\x00  Gómez ")

    assert usuario.nombre == "Ana Gómez"


def test_un_nombre_hecho_solo_de_caracteres_de_control_cuenta_como_vacio():
    with pytest.raises(usuarios.ErrorValidacion) as error:
        usuarios.crear("ana@x.com", "secreta123", "\x00\x00")
    assert "nombre" in error.value.errores


def test_login_con_caracter_nulo_no_es_un_error():
    usuarios.crear("ana@x.com", "secreta123", "Ana")

    assert usuarios.verificar("ana\x00@x.com", "secreta123") is None
    assert usuarios.verificar("ana@x.com", "secreta123\x00") is None
    assert usuarios.buscar_por_email("\x00") is None


def test_la_api_de_auth_responde_bien_con_caracteres_nulos():
    cliente = TestClient(app)

    r = cliente.post("/api/v1/auth/login", json={"email": "a\x00b@x.com", "password": "mala\x00"})
    assert r.status_code == 401
    r = cliente.post("/api/v1/auth/registro", json={"nombre": "Nu\x00lo", "email": "nulo\x00@x.com", "password": "secreta123"})
    assert r.status_code == 422 and "email" in r.json()["errores"]
    r = cliente.post("/api/v1/auth/registro", json={"nombre": "Nu\x00lo", "email": "nulo@x.com", "password": "secreta\x00123"})
    assert r.status_code == 201 and r.json()["nombre"] == "Nulo"
    # La contraseña se guarda como hash: el nulo forma parte de ella y sirve para entrar.
    assert cliente.post("/api/v1/auth/login", json={"email": "nulo@x.com", "password": "secreta\x00123"}).status_code == 200


def test_los_textos_de_la_app_se_guardan_sin_el_caracter_nulo():
    u = usuarios.crear("ana@x.com", "secreta123", "Ana").id
    hoy = movimientos.hoy()

    cuenta = cuentas.crear(u, CuentaEntrada(nombre="Aho\x00rros", tipo="ahorros", icono="banco", tono="azul", saldo=Decimal(1000)))
    categoria = categorias.crear(u, CategoriaEntrada(nombre="Mas\x00cotas", tipo="gasto"))
    movimiento = movimientos.crear(u, MovimientoEntrada(tipo="gasto", monto=Decimal(100), categoria_id=categoria.id,
                                                        cuenta_id=cuenta.id, fecha=hoy, descripcion="Con\x00centrado"))
    meta = metas.crear(u, MetaEntrada(nombre="Via\x00je", objetivo=Decimal(1000), fecha_limite=date(hoy.year + 1, 1, 1)))

    assert (cuenta.nombre, categoria.nombre, movimiento.descripcion, meta.nombre) == \
        ("Ahorros", "Mascotas", "Concentrado", "Viaje")
