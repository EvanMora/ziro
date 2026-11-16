"""Filtros de Jinja para mostrar dinero, porcentajes y fechas en español de Colombia."""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MENOS = "−"  # signo menos tipográfico, no guion


def dinero(valor: Decimal, signo: str = "") -> str:
    """$1.874.300. Con signo="+" o "−" antepone el signo; con signo="auto" lo pone solo si es negativo."""
    entero = int(Decimal(valor).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    texto = "$" + f"{abs(entero):,}".replace(",", ".")
    if signo == "auto":
        return (MENOS + texto) if entero < 0 else texto
    if signo == "-":
        signo = MENOS
    return signo + texto


def porcentaje(valor: float) -> str:
    """58,6 %: un decimal, coma decimal y espacio antes del símbolo."""
    return f"{valor:.1f}".replace(".", ",") + " %"


def fecha_corta(valor: date) -> str:
    """31 oct"""
    return f"{valor.day} {MESES_CORTOS[valor.month - 1]}"


def fecha_larga(valor: date) -> str:
    """Sábado 31 de octubre"""
    return f"{DIAS[valor.weekday()].capitalize()} {valor.day} de {MESES[valor.month - 1]}"


def nombre_mes(mes: int) -> str:
    return MESES[mes - 1]


def registrar(env) -> None:
    env.filters["dinero"] = dinero
    env.filters["porcentaje"] = porcentaje
    env.filters["fecha_corta"] = fecha_corta
    env.filters["fecha_larga"] = fecha_larga
    env.filters["nombre_mes"] = nombre_mes
