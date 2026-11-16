"""Reglas de las categorías: predeterminadas fijas, propias con nombre único por tipo, tipo fijo
si ya tienen movimientos y eliminación que pasa los movimientos a otra categoría."""
from datetime import date
from decimal import Decimal

import pytest

from app.schemas.categorias import CategoriaEntrada
from app.schemas.movimientos import FiltrosMovimientos, MovimientoEntrada
from app.services import categorias, movimientos
from app.services.comun import ErrorValidacion, NoEncontrado, NoPermitido
from tests import plantilla

U = 1


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 11, 15))


def nueva(nombre="Mascotas", tipo="gasto", usuario=U):
    return categorias.crear(usuario, CategoriaEntrada(nombre=nombre, tipo=tipo))


def movimiento(categoria_id, tipo="gasto", monto="50000"):
    return movimientos.crear(U, MovimientoEntrada(tipo=tipo, monto=Decimal(monto), categoria_id=categoria_id,
                                                  cuenta_id=1, fecha=date(2026, 10, 20)))


def errores(funcion, *args):
    with pytest.raises(ErrorValidacion) as e:
        funcion(*args)
    return e.value.errores


# ---------- Listar y crear ----------

def test_las_predeterminadas_vienen_marcadas():
    lista = categorias.listar(U)

    assert [c.nombre for c in lista] == ["Salario", "Otros ingresos", "Mercado", "Transporte", "Arriendo",
                                         "Ocio", "Otros gastos"]
    assert all(c.predeterminada for c in lista)


def test_crear_limpia_el_nombre_y_queda_en_el_catalogo_de_movimientos():
    creada = nueva("  Mascotas   y  veterinario ")

    assert creada.nombre == "Mascotas y veterinario"
    assert creada.predeterminada is False
    assert creada in categorias.listar(U)
    _, catalogo = movimientos.catalogo(U)
    assert catalogo[-1].model_dump() == {"id": creada.id, "nombre": "Mascotas y veterinario", "tipo": "gasto"}


def test_una_categoria_propia_se_usa_en_movimientos():
    creada = nueva()

    m = movimiento(creada.id)

    assert m.categoria.nombre == "Mascotas"


def test_las_categorias_propias_son_de_cada_usuario():
    plantilla.crear_usuario(2, "otra@correo.com", "Otra Persona")
    creada = nueva(usuario=2)

    assert creada not in categorias.listar(U)
    assert categorias.obtener(U, creada.id) is None
    with pytest.raises(NoEncontrado):
        categorias.eliminar(U, creada.id)


@pytest.mark.parametrize(
    ("nombre", "tipo", "mensaje"),
    [
        ("", "gasto", "Escribe un nombre."),
        ("    ", "gasto", "Escribe un nombre."),
        ("x" * 41, "gasto", "Máximo 40 caracteres."),
        ("mercado", "gasto", "Ya hay una categoría de gastos con ese nombre."),
        ("SALARIO", "ingreso", "Ya hay una categoría de ingresos con ese nombre."),
        ("Ocío", "gasto", "Ya hay una categoría de gastos con ese nombre."),
    ],
)
def test_nombre_invalido(nombre, tipo, mensaje):
    assert errores(nueva, nombre, tipo) == {"nombre": mensaje}


def test_el_mismo_nombre_puede_estar_en_el_otro_tipo():
    assert nueva("Mercado", "ingreso").tipo == "ingreso"


def test_maximo_de_categorias_propias(monkeypatch):
    monkeypatch.setattr(categorias, "MAX_PROPIAS", 2)
    nueva("Una")
    nueva("Dos")

    assert errores(nueva, "Tres") == {"general": "Llegaste al máximo de 2 categorías propias."}
    plantilla.crear_usuario(2, "otra@correo.com", "Otra Persona")
    assert nueva("Tres", usuario=2).nombre == "Tres"  # el límite es por usuario


# ---------- Editar ----------

def test_renombrar_cambia_el_nombre_en_sus_movimientos():
    creada = nueva()
    m = movimiento(creada.id)

    categorias.actualizar(U, creada.id, CategoriaEntrada(nombre="Gatos", tipo="gasto"))

    assert movimientos.obtener(U, m.id).categoria.nombre == "Gatos"
    buscados = movimientos.listar(U, 2026, 10, FiltrosMovimientos(q="gatos")).movimientos
    assert [x.id for x in buscados] == [m.id]


def test_renombrar_con_su_propio_nombre_no_es_duplicado():
    creada = nueva()

    assert categorias.actualizar(U, creada.id, CategoriaEntrada(nombre="mascotas", tipo="gasto")).nombre == "mascotas"


def test_el_tipo_cambia_solo_si_no_hay_movimientos():
    creada = nueva()
    assert categorias.actualizar(U, creada.id, CategoriaEntrada(nombre="Mascotas", tipo="ingreso")).tipo == "ingreso"

    movimiento(creada.id, tipo="ingreso")

    assert errores(categorias.actualizar, U, creada.id, CategoriaEntrada(nombre="Mascotas", tipo="gasto")) == {
        "tipo": "Ya tiene movimientos: el tipo no se puede cambiar."}


def test_las_predeterminadas_no_se_editan_ni_se_eliminan():
    with pytest.raises(NoPermitido):
        categorias.actualizar(U, 3, CategoriaEntrada(nombre="Comida", tipo="gasto"))
    with pytest.raises(NoPermitido):
        categorias.eliminar(U, 3)


def test_editar_inexistente():
    with pytest.raises(NoEncontrado):
        categorias.actualizar(U, 999, CategoriaEntrada(nombre="X", tipo="gasto"))


# ---------- Eliminar ----------

def test_eliminar_sin_movimientos():
    creada = nueva()

    categorias.eliminar(U, creada.id)

    assert categorias.obtener(U, creada.id) is None
    with pytest.raises(NoEncontrado):
        categorias.eliminar(U, creada.id)


def test_eliminar_con_movimientos_pide_a_donde_pasarlos():
    creada = nueva()
    movimiento(creada.id)
    movimiento(creada.id)

    assert errores(categorias.eliminar, U, creada.id) == {
        "mover_a": "Tiene 2 movimientos. Elige a qué categoría pasarlos."}
    assert categorias.obtener(U, creada.id) is not None


@pytest.mark.parametrize(("destino", "mensaje"), [
    (1, "Elige una categoría de gastos."),
    (999, "Elige otra categoría."),
    ("propia", "Elige otra categoría."),
])
def test_eliminar_con_destino_invalido(destino, mensaje):
    creada = nueva()
    movimiento(creada.id)

    mover_a = creada.id if destino == "propia" else destino
    assert errores(categorias.eliminar, U, creada.id, mover_a) == {"mover_a": mensaje}


def test_eliminar_pasa_los_movimientos_a_la_otra_categoria():
    creada = nueva()
    m = movimiento(creada.id)

    categorias.eliminar(U, creada.id, mover_a=6)

    assert categorias.obtener(U, creada.id) is None
    assert movimientos.obtener(U, m.id).categoria.model_dump() == {"id": 6, "nombre": "Ocio", "tipo": "gasto"}


def test_un_movimiento_no_puede_usar_una_categoria_eliminada():
    creada = nueva()
    categorias.eliminar(U, creada.id)

    with pytest.raises(ErrorValidacion) as e:
        movimiento(creada.id)
    assert e.value.errores == {"categoria_id": "Elige una categoría."}


# ---------- Cifras del mes ----------

def test_del_mes_suma_cuenta_y_ordena():
    creada = nueva()
    movimiento(creada.id, monto="10000")

    datos = categorias.del_mes(U, 2026, 10)

    gastos = [(g.categoria.nombre, g.total, g.movimientos) for g in datos.gastos]
    assert gastos == [
        ("Arriendo", Decimal("1100000"), 1),
        ("Mercado", Decimal("384300"), 2),
        ("Transporte", Decimal("210000"), 2),
        ("Ocio", Decimal("180000"), 2),
        ("Mascotas", Decimal("10000"), 1),
        ("Otros gastos", Decimal(0), 0),
    ]
    assert [(g.categoria.nombre, g.total) for g in datos.ingresos] == [
        ("Salario", Decimal("3200000")), ("Otros ingresos", Decimal(0))]
    assert datos.total_gastos == Decimal("1884300")
    assert datos.total_ingresos == Decimal("3200000")
    assert next(g for g in datos.gastos if g.categoria.id == creada.id).usos == 1


def test_usos_cuenta_movimientos_de_todos_los_meses():
    creada = nueva()
    movimiento(creada.id)
    movimientos.crear(U, MovimientoEntrada(tipo="gasto", monto=Decimal(1), categoria_id=creada.id, cuenta_id=1,
                                           fecha=date(2026, 9, 3)))

    fila = next(g for g in categorias.del_mes(U, 2026, 11).gastos if g.categoria.id == creada.id)

    assert (fila.movimientos, fila.usos, fila.total) == (0, 2, Decimal(0))
