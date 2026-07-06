"""Rutas de presupuesto: limite mensual por categoria con semaforo y ritmo."""
from datetime import datetime, timezone
from typing import Any, cast

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import auth
from ..categories import CATEGORIES
from ..dates import (
    MESES_CORTOS,
    meses_con_datos,
    month_bounds,
    month_label,
    parse_month_param,
    shift_month,
    today_bogota,
)
from ..db import get_supabase
from ..services.budgets import (
    dias_restantes_mes,
    gastado_por_categoria,
    pct_gastado,
    ritmo_diario,
    semaforo,
)
from ..templating import templates

router = APIRouter()


def _fetch_limites() -> dict[str, int]:
    filas = cast(
        "list[dict[str, Any]]",
        get_supabase().table("budgets").select("category, monthly_limit").execute().data,
    )
    return {f["category"]: int(f["monthly_limit"]) for f in filas}


def _meses_por_ano() -> dict[int, list[int]]:
    fechas = cast(
        "list[dict[str, Any]]",
        get_supabase().table("expenses").select("occurred_on").execute().data,
    )
    return meses_con_datos([f["occurred_on"] for f in fechas])


@router.get("/presupuesto", response_class=HTMLResponse)
def presupuesto(request: Request, mes: str | None = None):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    year, month = parse_month_param(mes)
    start, end = month_bounds(year, month)
    hoy = today_bogota()
    supa = get_supabase()

    gastos = cast(
        "list[dict[str, Any]]",
        supa.table("expenses")
        .select("category, amount")
        .gte("occurred_on", start.isoformat())
        .lte("occurred_on", end.isoformat())
        .execute()
        .data,
    )
    gastado = gastado_por_categoria(gastos)
    limites = _fetch_limites()

    filas = []
    total_presupuestado = 0
    total_gastado = 0
    for cat in CATEGORIES:
        limite = limites.get(cat, 0)
        gasto_cat = gastado.get(cat, 0)
        pct = pct_gastado(gasto_cat, limite)
        if limite > 0:
            total_presupuestado += limite
            total_gastado += gasto_cat
        filas.append(
            {
                "category": cat,
                "limite": limite,
                "gastado": gasto_cat,
                "pct": pct,
                "semaforo": semaforo(pct),
                "disponible": (limite - gasto_cat) if limite > 0 else None,
            }
        )

    disponible_total = total_presupuestado - total_gastado
    dias_restantes = dias_restantes_mes(hoy, year, month, end)
    ritmo = ritmo_diario(disponible_total, dias_restantes) if total_presupuestado > 0 else None

    return templates.TemplateResponse(
        request,
        "presupuesto.html",
        {
            "user": user,
            "active_tab": "presupuesto",
            "filas": filas,
            "total_presupuestado": total_presupuestado,
            "total_gastado": total_gastado,
            "disponible_total": disponible_total,
            "ritmo": ritmo,
            "base_path": "/presupuesto",
            "mes_actual": f"{year:04d}-{month:02d}",
            "mes_label": month_label(year, month),
            "mes_anterior": shift_month(year, month, -1),
            "mes_siguiente": shift_month(year, month, 1),
            "meses_por_ano": _meses_por_ano(),
            "meses_cortos": MESES_CORTOS,
        },
    )


@router.post("/presupuesto/{category}/editar")
def editar_limite(
    request: Request,
    category: str,
    monthly_limit: int = Form(..., ge=0),
    mes: str | None = Form(None),
):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    if category in CATEGORIES:
        get_supabase().table("budgets").upsert(
            {
                "category": category,
                "monthly_limit": monthly_limit,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="category",
        ).execute()

    destino = f"/presupuesto?mes={mes}" if mes else "/presupuesto"
    return RedirectResponse(destino, status_code=303)
