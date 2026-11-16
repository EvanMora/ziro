"""Lo que pinta la sección Metas a partir del panel (app/schemas/metas.py): el estado en palabras, la
línea de lo que falta y cuánto guardar, los últimos aportes y los datos para los diálogos. Aquí no se
consulta nada."""
from datetime import date

from app.schemas.metas import MetaConProgreso, PanelMetas
from app.web.formato import dinero, fecha_corta

ULTIMOS_APORTES = 4

# (texto del chip, clase): la clase da el color (ver metas.css).
_ESTADOS = {
    "al_dia": ("Vas al día", "ok"),
    "atrasada": ("Atrasada", "alerta"),  # la meta va atrasada (sin asumir el género de la persona)
    "sin_fecha": ("Sin fecha", "neutro"),
    "cumplida": ("¡Cumplida!", "cumplida"),
}


def _fecha(valor: date, hoy: date) -> str:
    """31 dic, o 1 mar 2027 si es de otro año."""
    return fecha_corta(valor) if valor.year == hoy.year else f"{fecha_corta(valor)} {valor.year}"


def _detalle(p: MetaConProgreso, hoy: date) -> str:
    if p.estado == "cumplida":
        return f"Llegaste a {dinero(p.meta.objetivo)}."
    falta = f"Te faltan {dinero(p.faltante)}"
    if p.estado == "vencida":
        return f"{falta}. Ponle una fecha nueva para seguir."
    if p.por_mes is None:
        return f"{falta}."
    if p.meses_restantes == 1:
        return f"{falta} · Guarda {dinero(p.por_mes)} este mes"
    return f"{falta} · Guarda {dinero(p.por_mes)} al mes hasta el {_fecha(p.meta.fecha_limite, hoy)}"


def _datos_meta(p: MetaConProgreso) -> dict:
    """Lo que necesitan los diálogos (va en data-meta)."""
    return {
        "id": p.meta.id,
        "nombre": p.meta.nombre,
        "objetivo": format(p.meta.objetivo, "f"),
        "fecha_limite": p.meta.fecha_limite.isoformat() if p.meta.fecha_limite else "",
        "creada_en": p.meta.creada_en.isoformat(),
        "ahorrado": format(p.ahorrado, "f"),
        "aportes": len(p.aportes),
    }


def vista_metas(panel: PanelMetas, hoy: date) -> dict:
    tarjetas = []
    for p in panel.metas:
        if p.estado == "vencida":
            chip = (f"Venció el {_fecha(p.meta.fecha_limite, hoy)}", "alerta")
        else:
            chip = _ESTADOS[p.estado]
        tarjetas.append({
            "p": p,
            "chip": chip[0],
            "clase": chip[1],
            "detalle": _detalle(p, hoy),
            "ancho": round(p.pct, 1),
            "datos": _datos_meta(p),
            "aportes": [{"a": a, "fecha": _fecha(a.fecha, hoy)} for a in p.aportes[:ULTIMOS_APORTES]],
            "mas_aportes": max(len(p.aportes) - ULTIMOS_APORTES, 0),
        })
    return {
        "tarjetas": tarjetas,
        "pct_total": round(float(panel.total_ahorrado / panel.total_objetivo * 100), 1) if panel.total_objetivo else 0.0,
    }
