"""Datos ya listos para las pantallas de Presupuestos. La plantilla solo
pinta: aquí se arman las semanas del calendario, la intensidad de cada día y los textos."""
from datetime import date
from decimal import Decimal

from app.schemas.presupuestos import PresupuestoDelMes
from app.web.formato import dinero, fecha_larga

DIAS_CORTOS = ["L", "M", "M", "J", "V", "S", "D"]
NIVELES = 4  # intensidad del fondo de un día con gastos: 1 (poco) a 4 (el día que más se gastó)


def corto(valor: Decimal) -> str:
    """Monto compacto para una celda del calendario: $950, $48 mil, $1,1 M."""
    v = Decimal(valor)
    if v >= 1_000_000:
        millones = (v / 1_000_000).quantize(Decimal("0.1"))
        texto = f"{millones}".replace(".", ",").removesuffix(",0")
        return f"${texto} M"
    if v >= 1000:
        return f"${int(v // 1000)} mil"
    return dinero(v)


def nota(restante: Decimal) -> str:
    """El texto bajo cada presupuesto: lo que queda o cuánto se pasó."""
    if restante < 0:
        return f"Te pasaste por {dinero(-restante)}"
    if restante == 0:
        return "Llegaste al límite"
    return f"Te quedan {dinero(restante)}"


def resumen(p: PresupuestoDelMes) -> dict:
    return {
        "nota": nota(p.restante),
        "ancho": min(p.pct, 100.0),
        "categorias": [
            {"c": c, "nota": nota(c.restante), "ancho": min(c.pct, 100.0)}
            for c in p.categorias
        ],
    }


def calendario(p: PresupuestoDelMes, hoy: date, gastos: list) -> dict:
    """Semanas de lunes a domingo; None en los huecos antes del día 1 y después del último."""
    maximo = max((d.total for d in p.dias), default=Decimal(0))
    por_dia: dict[date, list] = {}
    for m in gastos:
        por_dia.setdefault(m.fecha, []).append(m)

    celdas: list[dict | None] = [None] * p.dias[0].fecha.weekday()
    for d in p.dias:
        nivel = 0
        if d.total > 0 and maximo > 0:
            nivel = max(1, min(NIVELES, int((d.total / maximo) * NIVELES + Decimal("0.999"))))
        celdas.append({
            "dia": d.fecha.day,
            "iso": d.fecha.isoformat(),
            "total": d.total,
            "movimientos": d.movimientos,
            "nivel": nivel,
            "hoy": d.fecha == hoy,
            "futuro": d.fecha > hoy,
            "corto": corto(d.total),
        })
    celdas += [None] * (-len(celdas) % 7)

    # Detalle de cada día con gastos, para el panel que se abre al tocar el día (lo pinta el JS).
    detalle = {
        d.fecha.isoformat(): {
            "titulo": fecha_larga(d.fecha),
            "total": dinero(d.total, "-"),
            "items": [{"descripcion": m.descripcion or m.categoria.nombre, "categoria": m.categoria.nombre,
                       "cuenta": m.cuenta.nombre, "monto": dinero(m.monto, "-")}
                      for m in por_dia.get(d.fecha, [])],
        }
        for d in p.dias if d.total > 0
    }
    con_gasto = [d for d in p.dias if d.total > 0]
    pasados = [d for d in p.dias if d.fecha <= hoy]
    total = sum((d.total for d in p.dias), Decimal(0))
    return {
        "encabezado": DIAS_CORTOS,
        "semanas": [celdas[i:i + 7] for i in range(0, len(celdas), 7)],
        "total": total,
        "dias_con_gasto": len(con_gasto),
        "promedio": (total / len(pasados)) if pasados else Decimal(0),
        "mayor": max(con_gasto, key=lambda d: d.total) if con_gasto else None,
        "detalle": detalle,
        # Día que se muestra al abrir: hoy si tuvo gastos; si no, el último día con gastos.
        "inicial": next((d.fecha.isoformat() for d in reversed(con_gasto) if d.fecha <= hoy), None),
    }
