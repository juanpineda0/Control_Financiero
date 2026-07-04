"""Instancia de Jinja2Templates compartida por los routers, con el filtro `cop`.

Vive fuera de main.py para que los routers puedan importarla sin crear un import
circular (main.py es quien importa a los routers, no al reves).
"""
from pathlib import Path

from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def format_cop(amount) -> str:
    """1234567 -> "$1.234.567" (puntos de miles, sin decimales)."""
    try:
        return "${:,.0f}".format(amount).replace(",", ".")
    except (TypeError, ValueError):
        return "$0"


templates.env.filters["cop"] = format_cop
