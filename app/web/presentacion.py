"""Convierte los contratos en lo que necesitan las plantillas: porcentajes, alturas y anchos de
las gráficas del Resumen, los días agrupados de Movimientos y los grupos de Categorías. Aquí no
se consulta nada; solo se hacen cuentas de presentación."""
from datetime import date
from decimal import Decimal

from app.schemas.categorias import CategoriasDelMes
from app.schemas.cuentas import NOMBRE_TIPO, CuentaConSaldo, Pago, PanelCuentas
from app.schemas.dashboard import ResumenDashboard
from app.schemas.movimientos import ListaMovimientos, Movimiento
from app.web.formato import fecha_corta

ALTURA_CAPSULA = 200  # px de la cápsula más alta en "Ingresos vs. gastos"


def _pct(parte, total) -> float:
    return float(parte / total * 100) if total else 0.0


def vista_resumen(resumen: ResumenDashboard) -> dict:
    mayor_mes = max(resumen.ingresos_mes, resumen.gastos_mes)
    mayor_categoria = resumen.gastos_por_categoria[0].total if resumen.gastos_por_categoria else 0

    return {
        "queda": resumen.ingresos_mes - resumen.gastos_mes,
        "pct_gastado": _pct(resumen.gastos_mes, resumen.ingresos_mes),
        "altura_ingresos": round(_pct(resumen.ingresos_mes, mayor_mes) / 100 * ALTURA_CAPSULA),
        "altura_gastos": round(_pct(resumen.gastos_mes, mayor_mes) / 100 * ALTURA_CAPSULA),
        "categorias": [
            {
                "nombre": g.categoria,
                "total": g.total,
                "pct": _pct(g.total, resumen.gastos_mes),
                "ancho": round(_pct(g.total, mayor_categoria), 1),
                "mayor": i == 0,
            }
            for i, g in enumerate(resumen.gastos_por_categoria)
        ],
    }


def _neto(movimientos: list[Movimiento]) -> Decimal:
    return sum((m.monto if m.tipo == "ingreso" else -m.monto for m in movimientos), Decimal(0))


def datos_edicion(m: Movimiento) -> dict:
    """Lo que necesita el diálogo para abrir un movimiento en modo edición (va en data-movimiento)."""
    return {
        "id": m.id,
        "tipo": m.tipo,
        "monto": format(m.monto, "f"),  # nunca con exponente: el JS lee los dígitos
        "categoria_id": m.categoria.id,
        "cuenta_id": m.cuenta.id,
        "fecha": m.fecha.isoformat(),
        "descripcion": m.descripcion,
        "nombre": m.descripcion or m.categoria.nombre,
    }


def datos_pago_edicion(p: Pago) -> dict:
    """Lo que necesita el diálogo de pago para abrir un pago en modo edición (va en data-pago)."""
    return {
        "id": p.id,
        "tarjeta_id": p.tarjeta.id,
        "cuenta_origen_id": p.origen.id,
        "monto": format(p.monto, "f"),
        "fecha": p.fecha.isoformat(),
        "nombre": f"Pago {p.tarjeta.nombre}",
    }


def vista_movimientos(lista: ListaMovimientos, pagos: list[Pago] = ()) -> dict:
    """Días del más nuevo al más viejo. Los pagos de tarjeta van en su día, después de los
    movimientos, y no cuentan en el neto: no son gastos ni ingresos."""
    f = lista.filtros
    por_dia: dict[date, list[Movimiento]] = {}
    for m in lista.movimientos:
        por_dia.setdefault(m.fecha, []).append(m)
    pagos_por_dia: dict[date, list[Pago]] = {}
    for p in pagos:
        pagos_por_dia.setdefault(p.fecha, []).append(p)
    dias = []
    for fecha in sorted(por_dia.keys() | pagos_por_dia.keys(), reverse=True):
        movimientos = por_dia.get(fecha, [])
        dias.append({
            "fecha": fecha,
            "neto": _neto(movimientos),
            "filas": [{"m": m, "datos": datos_edicion(m)} for m in movimientos],
            "pagos": [{"p": p, "datos": datos_pago_edicion(p)} for p in pagos_por_dia.get(fecha, [])],
        })
    return {
        "dias": dias,
        "balance": lista.ingresos - lista.gastos,
        "hay_filtros": bool(f.tipo or f.cuenta_id or f.categoria_id or (f.q or "").strip()),
    }


def vista_categorias(datos: CategoriasDelMes) -> dict:
    """Gastos primero (como en los filtros de Movimientos), cada fila con su parte del total del
    grupo y lo que necesita el diálogo para editarla (va en data-categoria)."""
    grupos = []
    for tipo, titulo, filas, total in (("gasto", "Gastos", datos.gastos, datos.total_gastos),
                                       ("ingreso", "Ingresos", datos.ingresos, datos.total_ingresos)):
        grupos.append({
            "tipo": tipo,
            "titulo": titulo,
            "total": total,
            "filas": [
                {
                    "f": f,
                    "pct": _pct(f.total, total),
                    "datos": {"id": f.categoria.id, "nombre": f.categoria.nombre, "tipo": f.categoria.tipo,
                              "usos": f.usos},
                }
                for f in filas
            ],
        })
    return {"grupos": grupos}


DIAS_ALERTA = 5  # con deuda y a 5 días o menos de la fecha límite, la etiqueta va en alerta


def _decimal(valor: Decimal | None) -> str | None:
    return format(valor, "f") if valor is not None else None  # nunca con exponente: el JS lee los dígitos


def _datos_cuenta(c: CuentaConSaldo) -> dict:
    """Lo que necesita el diálogo para editar la cuenta (va en data-cuenta)."""
    return {
        "id": c.cuenta.id,
        "nombre": c.cuenta.nombre,
        "tipo": c.cuenta.tipo,
        "icono": c.cuenta.icono,
        "tono": c.cuenta.tono,
        "saldo": _decimal(c.saldo),
        "cupo": _decimal(c.cuenta.cupo),
        "dia_pago": c.cuenta.dia_pago,
        "usos": c.usos,
        "pagos": c.pagos,
    }


def _texto_fecha(t: CuentaConSaldo) -> str:
    if t.saldo <= 0:
        return "Al día"
    if t.dias_para_pagar == 0:
        return "Hoy"
    if t.dias_para_pagar == 1:
        return "Mañana"
    return f"Faltan {t.dias_para_pagar} días"


def vista_cuentas(panel: PanelCuentas) -> dict:
    """Filas de Dinero y de Tarjetas con lo que pintan la plantilla y los diálogos."""
    tarjetas = []
    for t in panel.tarjetas:
        tarjetas.append({
            "c": t,
            "datos": _datos_cuenta(t),
            "pct_usado": round(min(max(_pct(t.saldo, t.cuenta.cupo), 0.0), 100.0), 1),
            "con_deuda": t.saldo > 0,
            "alerta": t.saldo > 0 and t.dias_para_pagar <= DIAS_ALERTA,
            "excedido": t.disponible < 0,
            "texto_fecha": _texto_fecha(t),
        })
    return {
        "hay_cuentas": bool(panel.dinero or panel.tarjetas),
        "dinero": [{"c": c, "datos": _datos_cuenta(c), "tipo": NOMBRE_TIPO[c.cuenta.tipo]} for c in panel.dinero],
        "tarjetas": tarjetas,
    }


def datos_pago(panel: PanelCuentas) -> dict:
    """Cuentas de dinero (con saldo) y tarjetas (con deuda) para el diálogo de pago."""
    return {
        "dinero": [{"id": c.cuenta.id, "nombre": c.cuenta.nombre, "saldo": _decimal(c.saldo)} for c in panel.dinero],
        "tarjetas": [{"id": t.cuenta.id, "nombre": t.cuenta.nombre, "deuda": _decimal(t.saldo),
                      "fecha_texto": f"Pagar antes del {fecha_corta(t.fecha_limite)}" if t.saldo > 0 else "Al día"}
                     for t in panel.tarjetas],
    }
