"""Calculos puros para presupuestos por categoria: reciben dicts ya traidos de
Supabase y no tocan la base de datos.
"""
from datetime import date
from typing import Any


def gastado_por_categoria(gastos: list[dict[str, Any]]) -> dict[str, int]:
    resultado: dict[str, int] = {}
    for g in gastos:
        cat = g["category"]
        resultado[cat] = resultado.get(cat, 0) + int(g["amount"])
    return resultado


def pct_gastado(gastado: int, limite: int) -> float | None:
    """None si la categoria no tiene limite (sin presupuesto definido)."""
    if limite <= 0:
        return None
    return gastado / limite * 100


def semaforo(pct: float | None) -> str | None:
    """'verde' (<80%) / 'amarillo' (80-100%) / 'rojo' (>100%), o None sin limite."""
    if pct is None:
        return None
    if pct < 80:
        return "verde"
    if pct <= 100:
        return "amarillo"
    return "rojo"


def dias_restantes_mes(hoy: date, year: int, month: int, fin_mes: date) -> int | None:
    """Dias que quedan en el mes mostrado (contando hoy). None si el mes ya paso."""
    if (year, month) < (hoy.year, hoy.month):
        return None
    if (year, month) == (hoy.year, hoy.month):
        return max((fin_mes - hoy).days + 1, 1)
    return fin_mes.day


def ritmo_diario(disponible: int, dias_restantes: int | None) -> float | None:
    """Cuanto queda por gastar por dia para el resto del mes sin pasarse."""
    if dias_restantes is None or dias_restantes <= 0:
        return None
    return disponible / dias_restantes


def avisos_presupuesto(
    gastado: dict[str, int], limites: dict[str, int]
) -> list[dict[str, Any]]:
    """Categorias que ya pasaron el 80% del limite, para el aviso discreto en Gastos."""
    avisos = []
    for cat, limite in limites.items():
        if limite <= 0:
            continue
        pct = pct_gastado(gastado.get(cat, 0), limite)
        if pct is not None and pct >= 80:
            avisos.append({"category": cat, "pct": pct, "semaforo": semaforo(pct)})
    return sorted(avisos, key=lambda a: -a["pct"])
