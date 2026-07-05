"""Calculos puros para metas de ahorro/deuda: reciben dicts ya traidos de
Supabase y no tocan la base de datos.
"""
from datetime import date
from math import ceil
from typing import Any

from ..dates import add_months


def _as_date(valor: Any) -> date:
    return date.fromisoformat(valor) if isinstance(valor, str) else valor


def total_ahorrado(contribuciones: list[dict[str, Any]]) -> int:
    return sum(int(c["amount"]) for c in contribuciones)


def progreso_pct(ahorrado: int, target_amount: int) -> float:
    if target_amount <= 0:
        return 0.0
    return min(max(ahorrado / target_amount * 100, 0.0), 100.0)


def meses_restantes(hoy: date, target_date: date) -> int:
    meses = (target_date.year - hoy.year) * 12 + (target_date.month - hoy.month)
    if target_date.day > hoy.day:
        meses += 1
    return max(meses, 1)


def cuota_sugerida(
    ahorrado: int, target_amount: int, hoy: date, target_date: date | None
) -> int | None:
    """None si no hay fecha objetivo o si la meta ya se cumplio."""
    if target_date is None:
        return None
    restante = target_amount - ahorrado
    if restante <= 0:
        return None
    return ceil(restante / meses_restantes(hoy, target_date))


def esperado_a_hoy(
    target_amount: int, created_at: date, target_date: date | None, hoy: date
) -> int | None:
    """Progreso lineal esperado desde la creacion de la meta hasta la fecha objetivo."""
    if target_date is None or target_date <= created_at:
        return None
    total_dias = (target_date - created_at).days
    dias_transcurridos = min(max((hoy - created_at).days, 0), total_dias)
    return round(target_amount * dias_transcurridos / total_dias)


def estado_meta(ahorrado: int, target_amount: int, esperado: int | None) -> str | None:
    """'cumplida' / 'atrasado' / 'al_dia', o None si no hay progreso esperado (sin fecha)."""
    if ahorrado >= target_amount:
        return "cumplida"
    if esperado is None:
        return None
    return "atrasado" if ahorrado < esperado else "al_dia"


def desglose_por_persona(contribuciones: list[dict[str, Any]]) -> dict[str, int]:
    desglose: dict[str, int] = {}
    for c in contribuciones:
        desglose[c["user_name"]] = desglose.get(c["user_name"], 0) + int(c["amount"])
    return desglose


def ritmo_mensual_deuda(contribuciones: list[dict[str, Any]], hoy: date) -> float | None:
    """Total abonado / meses desde el primer aporte (minimo 1 mes)."""
    if not contribuciones:
        return None
    primera = min(_as_date(c["occurred_on"]) for c in contribuciones)
    meses = max((hoy.year - primera.year) * 12 + (hoy.month - primera.month), 1)
    return total_ahorrado(contribuciones) / meses


def fecha_estimada_pago(restante: int, ritmo_mensual: float | None, hoy: date) -> date | None:
    if not ritmo_mensual or ritmo_mensual <= 0 or restante <= 0:
        return None
    return add_months(hoy, ceil(restante / ritmo_mensual))
