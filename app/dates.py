"""Fecha y hora en zona horaria de Colombia, y utilidades de mes.

Vercel corre en UTC: sin esto, `date.today()` marca el dia siguiente para cualquiera
que use la app de noche en Colombia (UTC-5).
"""
from calendar import monthrange
from datetime import date, datetime
from zoneinfo import ZoneInfo

BOGOTA_TZ = ZoneInfo("America/Bogota")

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def today_bogota() -> date:
    return datetime.now(BOGOTA_TZ).date()


def parse_month_param(mes: str | None) -> tuple[int, int]:
    """Parsea 'YYYY-MM'; si falta o es invalido, usa el mes actual en Bogota."""
    if mes:
        try:
            year_str, month_str = mes.split("-")
            year, month = int(year_str), int(month_str)
            if 1 <= month <= 12:
                return year, month
        except ValueError:
            pass
    today = today_bogota()
    return today.year, today.month


def month_bounds(year: int, month: int) -> tuple[date, date]:
    """Primer y ultimo dia del mes."""
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def shift_month(year: int, month: int, delta: int) -> str:
    """Devuelve 'YYYY-MM' del mes desplazado `delta` meses (puede ser negativo)."""
    total = year * 12 + (month - 1) + delta
    new_year, remainder = divmod(total, 12)
    return f"{new_year:04d}-{remainder + 1:02d}"


def month_label(year: int, month: int) -> str:
    return f"{MESES[month - 1]} {year}"
