"""Servicio de metas de ahorro: reglas, aportes y retiros, progreso, cuánto guardar por mes y estado
(spec docs/superpowers/specs/2026-11-16-metas-design.md)."""
from datetime import date
from decimal import Decimal

import pytest

from app.schemas.metas import AporteEntrada, MetaEntrada
from app.services import metas, movimientos
from app.services.comun import ErrorValidacion, NoEncontrado
from tests import plantilla

U = plantilla.USUARIO_PRUEBA_ID
HOY = date(2026, 11, 16)


@pytest.fixture(autouse=True)
def _hoy(monkeypatch):
    monkeypatch.setattr(movimientos, "hoy", lambda: HOY)


def meta(nombre="Viaje", objetivo="2000000", fecha=date(2026, 12, 31), usuario=U):
    return metas.crear(usuario, MetaEntrada(nombre=nombre, objetivo=Decimal(objetivo), fecha_limite=fecha))


def aportar(m, monto, fecha=HOY, retiro=False, usuario=U):
    return metas.aportar(usuario, m.id, AporteEntrada(monto=Decimal(monto), fecha=fecha, retiro=retiro))


def errores(funcion, *args, **kwargs) -> dict:
    with pytest.raises(ErrorValidacion) as error:
        funcion(*args, **kwargs)
    return error.value.errores


def una(usuario=U):
    [m] = metas.panel(usuario).metas
    return m


# ---------- Crear y editar ----------

def test_crear_meta_empieza_en_cero():
    nueva = meta()

    m = una()
    assert m.meta.id == nueva.id
    assert m.meta.nombre == "Viaje"
    assert m.meta.creada_en == HOY
    assert (m.ahorrado, m.faltante, m.pct) == (Decimal(0), Decimal(2000000), 0.0)


@pytest.mark.parametrize(("cambios", "campo", "mensaje"), [
    ({"nombre": "  "}, "nombre", "Escribe un nombre."),
    ({"nombre": "x" * 41}, "nombre", "Máximo 40 caracteres."),
    ({"objetivo": Decimal(0)}, "objetivo", "Escribe un objetivo mayor que 0."),
    ({"objetivo": Decimal(-5)}, "objetivo", "Escribe un objetivo mayor que 0."),
    ({"objetivo": Decimal("1E+12")}, "objetivo", "El monto es demasiado grande."),
    ({"fecha_limite": date(2026, 11, 15)}, "fecha_limite", "La fecha límite no puede ser pasada."),
    ({"fecha_limite": date(2080, 1, 1)}, "fecha_limite", "Elige una fecha de los próximos 50 años."),
])
def test_reglas_de_la_meta(cambios, campo, mensaje):
    datos = {"nombre": "Viaje", "objetivo": Decimal(1000), "fecha_limite": None} | cambios
    assert errores(metas.crear, U, MetaEntrada(**datos)) == {campo: mensaje}


def test_nombre_unico_sin_tildes_ni_mayusculas():
    meta("Vacaciones en Cartagena")

    assert errores(meta, "VACACIONES en cartagená") == {"nombre": "Ya tienes una meta con ese nombre."}


def test_la_fecha_limite_es_opcional_y_puede_ser_hoy():
    meta("Sin fecha", fecha=None)
    meta("Hoy", fecha=HOY)

    assert len(metas.panel(U).metas) == 2


def test_maximo_de_metas(monkeypatch):
    monkeypatch.setattr(metas, "MAX_METAS", 2)
    meta("Una")
    meta("Dos")

    assert errores(meta, "Tres") == {"general": "Llegaste al máximo de 2 metas."}


def test_editar_conserva_aportes_y_permite_fecha_vieja_sin_cambiarla(monkeypatch):
    m = meta(fecha=date(2026, 11, 20))
    aportar(m, "100000")
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 12, 5))  # la fecha ya pasó

    metas.actualizar(U, m.id, MetaEntrada(nombre="Viaje a Santa Marta", objetivo=Decimal(3000000),
                                          fecha_limite=date(2026, 11, 20)))
    m2 = una()
    assert (m2.meta.nombre, m2.meta.objetivo, m2.ahorrado) == ("Viaje a Santa Marta", Decimal(3000000), Decimal(100000))

    # Cambiarla a otra fecha pasada no se puede.
    assert "fecha_limite" in errores(metas.actualizar, U, m.id, MetaEntrada(
        nombre="Viaje", objetivo=Decimal(3000000), fecha_limite=date(2026, 11, 25)))


def test_editar_el_nombre_de_otra_meta_repetido():
    meta("Viaje")
    otra = meta("Carro")

    assert errores(metas.actualizar, U, otra.id, MetaEntrada(nombre="viaje", objetivo=Decimal(1), fecha_limite=None)) \
        == {"nombre": "Ya tienes una meta con ese nombre."}


def test_eliminar_borra_sus_aportes():
    m = meta()
    aportar(m, "100000")

    metas.eliminar(U, m.id)
    assert metas.panel(U).metas == []
    with pytest.raises(NoEncontrado):
        metas.eliminar(U, m.id)


# ---------- Aportes y retiros ----------

def test_aportes_y_retiros_suman_al_ahorrado():
    m = meta()
    aportar(m, "500000", date(2026, 11, 16))
    aportar(m, "250000.50", date(2026, 11, 16))
    aportar(m, "50000", retiro=True)

    actual = una()
    assert actual.ahorrado == Decimal("700000.50")
    assert actual.faltante == Decimal("1299999.50")
    assert actual.pct == pytest.approx(35.0, abs=0.01)
    # Del más nuevo al más viejo; el retiro va en negativo.
    assert [a.monto for a in actual.aportes] == [Decimal(-50000), Decimal("250000.50"), Decimal(500000)]


@pytest.mark.parametrize(("monto", "fecha", "campo", "mensaje"), [
    ("0", HOY, "monto", "Escribe un monto mayor que 0."),
    ("-1", HOY, "monto", "Escribe un monto mayor que 0."),
    ("1E+12", HOY, "monto", "El monto es demasiado grande."),
    ("1000", date(2026, 11, 17), "fecha", "La fecha no puede ser futura."),
    ("1000", date(2026, 11, 15), "fecha", "La meta se creó el 16 nov: elige esa fecha o una posterior."),
])
def test_reglas_del_aporte(monto, fecha, campo, mensaje):
    m = meta()
    assert errores(aportar, m, monto, fecha) == {campo: mensaje}


def test_no_se_retira_mas_de_lo_ahorrado():
    m = meta()
    aportar(m, "100000")

    assert errores(aportar, m, "100001", retiro=True) == {"monto": "Solo tienes $100.000 ahorrados en esta meta."}
    aportar(m, "100000", retiro=True)
    assert una().ahorrado == 0


def test_borrar_un_aporte():
    m = meta()
    a = aportar(m, "100000")
    aportar(m, "30000")

    metas.eliminar_aporte(U, m.id, a.id)
    assert una().ahorrado == Decimal(30000)


def test_borrar_un_aporte_no_deja_el_ahorrado_negativo():
    m = meta()
    a = aportar(m, "100000")
    aportar(m, "80000", retiro=True)

    assert errores(metas.eliminar_aporte, U, m.id, a.id) == {
        "general": "Si lo borras, lo ahorrado quedaría en negativo. Borra primero el retiro."}


def test_aporte_de_otra_meta_no_se_borra_por_la_equivocada():
    m1, m2 = meta("Uno"), meta("Dos")
    a = aportar(m1, "1000")

    with pytest.raises(NoEncontrado):
        metas.eliminar_aporte(U, m2.id, a.id)


# ---------- Progreso, por mes y estado ----------

def test_por_mes_cuenta_el_mes_actual_y_redondea_hacia_arriba():
    meta(objetivo="1000000", fecha=date(2027, 1, 10))  # nov, dic y ene: 3 meses

    m = una()
    assert m.meses_restantes == 3
    assert m.por_mes == Decimal(333334)


def test_meta_cumplida_no_pide_mas():
    m = meta(objetivo="100000")
    aportar(m, "150000")

    actual = una()
    assert actual.estado == "cumplida"
    assert actual.faltante == 0
    assert actual.pct == 100.0
    assert actual.por_mes is None


def test_sin_fecha():
    meta(fecha=None)

    m = una()
    assert (m.estado, m.por_mes, m.meses_restantes) == ("sin_fecha", None, None)


def test_vencida(monkeypatch):
    meta(fecha=date(2026, 11, 30))
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2026, 12, 1))

    m = una()
    assert (m.estado, m.por_mes) == ("vencida", None)


def test_atrasada_y_al_dia(monkeypatch):
    # 100 días para 1.000.000: a los 50 días se esperan 500.000.
    m = meta(objetivo="1000000", fecha=date(2027, 2, 24))
    aportar(m, "400000")
    monkeypatch.setattr(movimientos, "hoy", lambda: date(2027, 1, 5))
    assert una().estado == "atrasada"

    aportar(m, "100000", date(2027, 1, 5))
    assert una().estado == "al_dia"


def test_recien_creada_esta_al_dia():
    meta()
    assert una().estado == "al_dia"


def test_orden_por_fecha_y_cumplidas_al_final():
    sin = meta("Sin fecha", fecha=None)
    lejos = meta("Lejos", fecha=date(2027, 6, 1))
    cerca = meta("Cerca", fecha=date(2026, 12, 1))
    lista = meta("Lista", objetivo="10", fecha=date(2026, 11, 20))
    aportar(lista, "10")

    assert [m.meta.id for m in metas.panel(U).metas] == [cerca.id, lejos.id, sin.id, lista.id]


def test_totales_del_panel():
    m1, m2 = meta("Uno", objetivo="1000"), meta("Dos", objetivo="3000")
    aportar(m1, "500")
    aportar(m2, "250")

    p = metas.panel(U)
    assert (p.total_ahorrado, p.total_objetivo) == (Decimal(750), Decimal(4000))


def test_las_metas_no_tocan_las_cuentas_ni_el_mes():
    from app.services import cuentas
    antes = cuentas.panel(U).tienes, movimientos.listar(U, 2026, 11).gastos
    m = meta()
    aportar(m, "500000")

    assert (cuentas.panel(U).tienes, movimientos.listar(U, 2026, 11).gastos) == antes


# ---------- Cada quien sus metas ----------

def test_metas_por_usuario():
    plantilla.crear_usuario(2, "otra@correo.com", "Otra Persona")
    m = meta()

    assert metas.panel(2).metas == []
    with pytest.raises(NoEncontrado):
        aportar(m, "1000", usuario=2)
    with pytest.raises(NoEncontrado):
        metas.actualizar(2, m.id, MetaEntrada(nombre="Robada", objetivo=Decimal(1), fecha_limite=None))
    with pytest.raises(NoEncontrado):
        metas.eliminar(2, m.id)
    meta("Viaje", usuario=2)  # el nombre es único por persona, no global
