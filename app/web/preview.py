"""Datos de ejemplo y geometría para la vista previa decorativa del dashboard en el login.

Los números son coherentes entre sí: el ahorro de octubre es ingresos − gastos, los gastos
por categoría suman el gasto del mes y los presupuestos usan esas mismas categorías.
"""

from functools import cache

MONTHS = ["nov", "dic", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct"]
SAVINGS = [420_000, 260_000, 610_000, 540_000, 390_000, 720_000, 680_000, 510_000, 830_000, 760_000, 1_180_000]
BALANCE = [2_310_000, 2_420_000, 2_650_000, 2_580_000, 2_890_000, 3_020_000, 2_950_000, 3_210_000,
           3_480_000, 3_610_000, 3_890_000, 4_382_900]
INCOME = 3_200_000
EXPENSES_BY_CATEGORY = [("Arriendo", 1_100_000), ("Mercado", 384_300), ("Transporte", 210_000), ("Ocio", 180_000)]
BUDGETS = [("Transporte", 210_000, 300_000), ("Mercado", 384_300, 470_000), ("Ocio", 180_000, 150_000)]
MOVEMENTS = [("Salario", INCOME, "income"), ("Arriendo", -1_100_000, "home"),
             ("Mercado", -184_300, "cart"), ("Transporte", -62_000, "bus")]

SPARK_WIDTH, SPARK_HEIGHT, SPARK_PAD = 228, 56, 6


def money(value, sign=False):
    text = f"${abs(value):,}".replace(",", ".")
    if sign:
        return ("+" if value >= 0 else "−") + text
    return text


def _sparkline():
    low, high = min(BALANCE), max(BALANCE)
    step = (SPARK_WIDTH - 2 * SPARK_PAD) / (len(BALANCE) - 1)
    points = [
        (SPARK_PAD + i * step, SPARK_PAD + (high - v) / (high - low) * (SPARK_HEIGHT - 2 * SPARK_PAD))
        for i, v in enumerate(BALANCE)
    ]
    line = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points)
    area = f"{line} L{points[-1][0]:.1f},{SPARK_HEIGHT} L{points[0][0]:.1f},{SPARK_HEIGHT} Z"
    return {"line": line, "area": area, "end": points[-1], "width": SPARK_WIDTH, "height": SPARK_HEIGHT}


# Solo depende de constantes: se calcula una vez. La plantilla solo lee el resultado; no mutarlo.
@cache
def build_preview():
    expenses = sum(amount for _, amount in EXPENSES_BY_CATEGORY)
    savings = SAVINGS + [INCOME - expenses]
    top_saving = max(savings)
    top_category = EXPENSES_BY_CATEGORY[0][1]
    delta = (BALANCE[-1] - BALANCE[-2]) / BALANCE[-2] * 100

    budgets = []
    for name, spent, limit in BUDGETS:
        pct = round(spent / limit * 100)
        status = "danger" if pct > 100 else "warning" if pct >= 80 else "ok"
        budgets.append({
            "name": name, "pct": pct, "fill": min(pct, 100), "status": status,
            "note": {"danger": f"Excedido por {money(spent - limit)}",
                     "warning": f"Te quedan {money(limit - spent)}",
                     "ok": f"Te quedan {money(limit - spent)}"}[status],
        })

    return {
        "balance": BALANCE[-1],
        "balance_text": money(BALANCE[-1]),
        "delta_text": f"{delta:.1f}".replace(".", ",") + " %",
        "income_text": money(INCOME, sign=True),
        "expenses_text": money(-expenses, sign=True),
        "spark": _sparkline(),
        "savings": [
            # Fondo decorativo: altura mínima del 45 % para que todos los paneles tengan color detrás.
            {"month": m, "height": round(45 + v / top_saving * 55, 1), "current": i == len(savings) - 1}
            for i, (m, v) in enumerate(zip(MONTHS, savings))
        ],
        "categories": [
            {"name": n, "amount": money(a), "width": round(a / top_category * 100, 1), "top": i == 0}
            for i, (n, a) in enumerate(EXPENSES_BY_CATEGORY)
        ],
        "budgets": budgets,
        "movements": [{"name": n, "amount": money(a, sign=True), "income": a > 0, "icon": icon}
                      for n, a, icon in MOVEMENTS],
    }
