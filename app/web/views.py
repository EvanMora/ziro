"""Rutas que devuelven HTML renderizado con Jinja2."""
import os
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.schemas.movimientos import FiltrosMovimientos
from app.services import categorias as categorias_servicio
from app.services import cuentas as cuentas_servicio
from app.services import ia as ia_servicio
from app.services import movimientos as movimientos_servicio
from app.services import presupuestos as presupuestos_servicio
from app.services.dashboard import obtener_resumen
from app.web import formato, presupuestos_vista
from app.web.presentacion import (
    datos_pago,
    vista_categorias,
    vista_cuentas,
    vista_movimientos,
    vista_resumen,
)
from app.web.preview import build_preview
from app.web.sesion import USUARIO_DEMO

APP_DIR = Path(__file__).resolve().parent.parent

templates = Jinja2Templates(directory=APP_DIR / "templates")
# Nombre provisional: el equipo aún no lo define (ver docs/alcance.md, decisiones pendientes).
templates.env.globals["app_name"] = "Ziro"
formato.registrar(templates.env)
# Revisar en cada petición si una plantilla cambió en disco cuesta 8 stat por página. Solo hace falta
# en desarrollo: "fastapi dev" pone FASTAPI_ENV=development antes de importar la app (ver .env.example).
templates.env.auto_reload = os.environ.get("FASTAPI_ENV") == "development"
# Sin la línea en blanco ni la sangría que deja cada {% ... %}: medio KB menos por página, más o menos.
templates.env.trim_blocks = templates.env.lstrip_blocks = True


def static(path: str) -> str:
    """URL de un archivo de app/static: static('css/app.css') → "/static/css/app.css". Hace lo mismo
    que url_for('static', path=...) sin recorrer las rutas de Starlette en cada llamada (era la mitad
    del render), y la deja relativa al sitio en vez de http://host/static/.... Debe coincidir con el
    app.mount("/static", ...) de app/main.py (lo revisa tests/test_rendimiento_a8.py)."""
    return "/static/" + path


templates.env.globals["static"] = static

router = APIRouter(include_in_schema=False)

# Cookie que recuerda la barra lateral contraída; la escribe static/js/app-shell.js.
COOKIE_BARRA = "barra_contraida"

# Secciones de la barra lateral: (ruta, nombre, ícono). El orden es el de la barra.
SECCIONES = [
    ("resumen", "Resumen", "resumen"),
    ("movimientos", "Movimientos", "movimientos"),
    ("cuentas", "Cuentas", "cuentas"),
    ("categorias", "Categorías", "categorias"),
    ("presupuestos", "Presupuestos", "presupuestos"),
]
PROXIMAMENTE = [("Metas", "metas")]



def _grupos_cuentas(lista: list) -> list[tuple[str, list]]:
    """Las cuentas (de cuentas.listar) para los <select>, en <optgroup> "Dinero" y "Tarjetas" (sin
    grupos vacíos)."""
    grupos = [("Dinero", [cuentas_servicio.ref(c) for c in lista if not cuentas_servicio.es_tarjeta(c.tipo)]),
              ("Tarjetas", [cuentas_servicio.ref(c) for c in lista if cuentas_servicio.es_tarjeta(c.tipo)])]
    return [(nombre, refs) for nombre, refs in grupos if refs]


def _contexto_app(request: Request, seccion: str, *, hoy: date | None = None, cuentas: list | None = None,
                  categorias: list | None = None) -> dict:
    """Lo común a todas las secciones. hoy, cuentas (cuentas.listar) y categorias (categorias.listar):
    si la ruta ya los leyó, para no leerlos otra vez en la misma petición."""
    usuario = USUARIO_DEMO["id"]
    cuentas = cuentas_servicio.listar(usuario) if cuentas is None else cuentas
    categorias = categorias_servicio.listar(usuario) if categorias is None else categorias
    hoy = hoy or movimientos_servicio.hoy()
    return {
        "seccion": seccion,
        "secciones": SECCIONES,
        "proximamente": PROXIMAMENTE,
        "usuario": USUARIO_DEMO,
        "barra_contraida": request.cookies.get(COOKIE_BARRA) == "1",
        # Para el diálogo "Nuevo movimiento", que está en todas las secciones.
        "grupos_cuentas": _grupos_cuentas(cuentas),
        "catalogo_categorias": [categorias_servicio.ref(c) for c in categorias],  # como movimientos.catalogo
        "hoy_iso": hoy.isoformat(),
        # El asistente con Gemini solo aparece si hay GEMINI_API_KEY.
        "ia_disponible": ia_servicio.configurado(),
    }


def _periodo(anio: int | None, mes: int | None, hoy: date | None = None) -> tuple[int, int]:
    """Mes pedido, o el actual si no se pide ninguno. No deja ir a meses futuros. Usa la fecha de
    la app (movimientos.hoy), como el resto de las cuentas; la ruta la puede pasar si ya la leyó."""
    hoy = hoy or movimientos_servicio.hoy()
    if anio is None or mes is None:
        return hoy.year, hoy.month
    return min((anio, mes), (hoy.year, hoy.month))


def _mes_de_url(anio: str | None, mes: str | None, hoy: date | None = None) -> tuple[int, int]:
    """El mes de ?anio=&mes=. Si alguno falta o no es válido (mes=13, anio=abc), el mes actual:
    una URL mal escrita muestra la página, no un error en JSON."""
    a, m = _entero(anio), _entero(mes)
    if a is None or m is None or not (2000 <= a <= 2100 and 1 <= m <= 12):
        return _periodo(None, None, hoy)
    return _periodo(a, m, hoy)


def _navegacion_mes(anio: int, mes: int, hoy: date | None = None) -> dict:
    hoy = hoy or movimientos_servicio.hoy()
    anterior = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
    siguiente = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return {
        "anio": anio,
        "mes": mes,
        "anterior": anterior,
        "siguiente": siguiente if siguiente <= (hoy.year, hoy.month) else None,
    }


@router.get("/login", response_class=HTMLResponse)
def login(request: Request):
    context = {"year": date.today().year, "preview": build_preview()}
    return templates.TemplateResponse(request, "login.html", context)


@router.get("/resumen", response_class=HTMLResponse)
def resumen(
    request: Request,
    anio: str | None = None,
    mes: str | None = None,
):
    # Lo que usan varias partes de la página se lee una sola vez: la fecha, las cuentas, las
    # categorías y los movimientos del mes (los usan el Resumen y el presupuesto).
    usuario = USUARIO_DEMO["id"]
    hoy = movimientos_servicio.hoy()
    anio, mes = _mes_de_url(anio, mes, hoy)
    cuentas = cuentas_servicio.listar(usuario)
    categorias = categorias_servicio.listar(usuario)
    lista = movimientos_servicio.listar(usuario, anio, mes)
    datos = obtener_resumen(usuario, anio, mes, lista=lista, lista_cuentas=cuentas)
    presupuesto = presupuestos_servicio.del_mes(
        usuario, anio, mes, gastos=presupuestos_servicio.gastos_del_mes(usuario, anio, mes, lista=lista),
        lista_categorias=categorias)
    context = _contexto_app(request, "resumen", hoy=hoy, cuentas=cuentas, categorias=categorias) | {
        "resumen": datos,
        "vista": vista_resumen(datos),
        "periodo": _navegacion_mes(anio, mes, hoy),
        "presupuesto": presupuesto,
        "vista_presupuesto": presupuestos_vista.resumen(presupuesto),
        "es_mes_actual": (anio, mes) == (hoy.year, hoy.month),
    }
    return templates.TemplateResponse(request, "app/resumen.html", context)


def _entero(valor: str | None) -> int | None:
    """Número de la URL, o None. No usa str.isdigit(): acepta "²" y luego int() falla."""
    return int(valor) if valor and re.fullmatch(r"[0-9]{1,9}", valor) else None


def _id_valido(valor: str | None, validos: set[int]) -> int | None:
    """Un id de la URL solo cuenta si es un número que existe en el catálogo; si no, se ignora."""
    numero = _entero(valor)
    return numero if numero in validos else None


def _filtros(tipo: str | None, cuenta: str | None, categoria: str | None, q: str | None) -> FiltrosMovimientos:
    cuentas, categorias = movimientos_servicio.catalogo(USUARIO_DEMO["id"])
    texto = (q or "").strip()[:80]
    return FiltrosMovimientos(
        tipo=tipo if tipo in ("ingreso", "gasto") else None,
        cuenta_id=_id_valido(cuenta, {c.id for c in cuentas}),
        categoria_id=_id_valido(categoria, {c.id for c in categorias}),
        q=texto or None,
    )


def _consulta(f: FiltrosMovimientos) -> str:
    """Los filtros activos como parámetros de URL, para que el selector de mes los conserve."""
    pares = {"tipo": f.tipo, "cuenta": f.cuenta_id, "categoria": f.categoria_id, "q": f.q}
    return urlencode({k: v for k, v in pares.items() if v})


@router.get("/movimientos", response_class=HTMLResponse)
def movimientos(
    request: Request,
    anio: str | None = None,
    mes: str | None = None,
    tipo: str | None = None,
    cuenta: str | None = None,
    categoria: str | None = None,
    q: str | None = None,
    nuevo: str | None = None,
    guardado: str | None = None,
):
    anio, mes = _mes_de_url(anio, mes)
    filtros = _filtros(tipo, cuenta, categoria, q)
    lista = movimientos_servicio.listar(USUARIO_DEMO["id"], anio, mes, filtros)
    pagos = cuentas_servicio.pagos_del_mes(USUARIO_DEMO["id"], anio, mes, filtros)
    _, categorias = movimientos_servicio.catalogo(USUARIO_DEMO["id"])
    context = _contexto_app(request, "movimientos") | {
        "lista": lista,
        "vista": vista_movimientos(lista, pagos),
        "pago": datos_pago(cuentas_servicio.panel(USUARIO_DEMO["id"])),
        "periodo": _navegacion_mes(anio, mes),
        "consulta": _consulta(filtros),
        "categorias": categorias,
        "abrir_dialogo": nuevo == "1",
        "guardado": _entero(guardado),
    }
    return templates.TemplateResponse(request, "app/movimientos.html", context)


@router.get("/cuentas", response_class=HTMLResponse)
def cuentas(request: Request, guardado: str | None = None):
    panel = cuentas_servicio.panel(USUARIO_DEMO["id"])
    context = _contexto_app(request, "cuentas") | {
        "panel": panel,
        "vista": vista_cuentas(panel),
        "pago": datos_pago(panel),
        "guardado": _entero(guardado),
    }
    return templates.TemplateResponse(request, "app/cuentas.html", context)


@router.get("/categorias", response_class=HTMLResponse)
def categorias(
    request: Request,
    anio: str | None = None,
    mes: str | None = None,
    guardado: str | None = None,
):
    anio, mes = _mes_de_url(anio, mes)
    datos = categorias_servicio.del_mes(USUARIO_DEMO["id"], anio, mes)
    context = _contexto_app(request, "categorias") | {
        "datos": datos,
        "vista": vista_categorias(datos),
        "periodo": _navegacion_mes(anio, mes),
        "guardado": _entero(guardado),
    }
    return templates.TemplateResponse(request, "app/categorias.html", context)


# ---------- Presupuestos ----------

@router.get("/presupuestos", response_class=HTMLResponse)
def presupuestos(request: Request, anio: str | None = None, mes: str | None = None):
    anio, mes = _mes_de_url(anio, mes)
    hoy = movimientos_servicio.hoy()
    usuario = USUARIO_DEMO["id"]
    gastos = presupuestos_servicio.gastos_del_mes(usuario, anio, mes)
    datos = presupuestos_servicio.del_mes(usuario, anio, mes, gastos=gastos)  # sin listar el mes otra vez
    context = _contexto_app(request, "presupuestos") | {
        "datos": datos,
        "vista": presupuestos_vista.resumen(datos),
        "cal": presupuestos_vista.calendario(datos, hoy, gastos),
        "periodo": _navegacion_mes(anio, mes),
        "es_mes_actual": (anio, mes) == (hoy.year, hoy.month),
    }
    return templates.TemplateResponse(request, "app/presupuestos.html", context)


@router.get("/presupuestos/nuevo", response_class=HTMLResponse)
def presupuesto_nuevo(request: Request, anio: str | None = None, mes: str | None = None,
                      volver: str | None = None):
    """Crear (o editar) el presupuesto del mes: un monto por categoría de gasto. "volver" es la
    pantalla a la que se regresa al guardar o cancelar: el Resumen o Presupuestos (la de siempre)."""
    anio, mes = _mes_de_url(anio, mes)
    if volver != "resumen":
        volver = "presupuestos"
    usuario = USUARIO_DEMO["id"]
    actual = presupuestos_servicio.del_mes(usuario, anio, mes)
    limites = {c.categoria.id: c.limite for c in actual.categorias}
    ant_anio, ant_mes = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
    anterior = {f.categoria.id: f.total for f in categorias_servicio.del_mes(usuario, ant_anio, ant_mes).gastos}
    filas = [{"categoria": c, "limite": limites.get(c.id), "mes_anterior": anterior.get(c.id, 0)}
             for c in categorias_servicio.listar(usuario) if c.tipo == "gasto"]
    context = _contexto_app(request, volver) | {
        "anio": anio,
        "mes": mes,
        "mes_anterior": ant_mes,
        "editando": actual.creado,
        "filas": filas,
        "total": actual.total,
        "volver": f"/{volver}?anio={anio}&mes={mes}",
    }
    return templates.TemplateResponse(request, "app/presupuesto_nuevo.html", context)
