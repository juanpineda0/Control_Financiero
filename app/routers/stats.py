"""Rutas de estadisticas: vista mensual (dashboard) y vista anual."""
from typing import Any, cast

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import auth
from ..dates import (
    MESES,
    MESES_CORTOS,
    meses_con_datos,
    month_bounds,
    month_label,
    parse_month_param,
    shift_month,
    today_bogota,
)
from ..db import get_supabase
from ..services.stats import (
    compartido_vs_no,
    delta_por_categoria,
    dias_transcurridos_mes,
    por_categoria,
    por_dia,
    por_metodo_pago,
    por_persona,
    por_quincena,
    proyeccion_cierre,
    promedio_diario,
    promedio_mensual_por_categoria,
    top_gastos,
    total_gastado,
    total_por_mes,
)
from ..templating import templates

router = APIRouter()


def _meses_por_ano() -> dict[int, list[int]]:
    fechas = cast(
        "list[dict[str, Any]]",
        get_supabase().table("expenses").select("occurred_on").execute().data,
    )
    return meses_con_datos([f["occurred_on"] for f in fechas])


@router.get("/stats", response_class=HTMLResponse)
def stats_mes(request: Request, mes: str | None = None):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    year, month = parse_month_param(mes)
    start, end = month_bounds(year, month)
    dias_totales = (end - start).days + 1
    hoy = today_bogota()
    supa = get_supabase()

    gastos_mes = cast(
        "list[dict[str, Any]]",
        supa.table("expenses")
        .select("*")
        .gte("occurred_on", start.isoformat())
        .lte("occurred_on", end.isoformat())
        .execute()
        .data,
    )

    anio_ant, mes_ant = (year - 1, 12) if month == 1 else (year, month - 1)
    start_ant, end_ant = month_bounds(anio_ant, mes_ant)
    gastos_mes_anterior = cast(
        "list[dict[str, Any]]",
        supa.table("expenses")
        .select("category, amount")
        .gte("occurred_on", start_ant.isoformat())
        .lte("occurred_on", end_ant.isoformat())
        .execute()
        .data,
    )

    total = total_gastado(gastos_mes)
    total_anterior = total_gastado(gastos_mes_anterior)
    dias_transcurridos = dias_transcurridos_mes(hoy, year, month, dias_totales)

    cat_actual = por_categoria(gastos_mes)
    cat_anterior = por_categoria(gastos_mes_anterior)
    deltas = delta_por_categoria(cat_actual, cat_anterior)
    subidas = [d for d in deltas if d["delta"] > 0]
    bajadas = [d for d in deltas if d["delta"] < 0]

    return templates.TemplateResponse(
        request,
        "stats.html",
        {
            "user": user,
            "active_tab": "stats",
            "base_path": "/stats",
            "mes_actual": f"{year:04d}-{month:02d}",
            "mes_label": month_label(year, month),
            "mes_anterior": shift_month(year, month, -1),
            "mes_siguiente": shift_month(year, month, 1),
            "meses_por_ano": _meses_por_ano(),
            "meses_cortos": MESES_CORTOS,
            "anio_actual": year,
            "total": total,
            "total_anterior": total_anterior,
            "delta_total": total - total_anterior,
            "dias_totales": dias_totales,
            "dias_transcurridos": dias_transcurridos,
            "promedio": promedio_diario(total, dias_transcurridos),
            "proyeccion": proyeccion_cierre(total, dias_transcurridos, dias_totales),
            "por_categoria": cat_actual,
            "delta_categoria": deltas,
            "delta_labels": [d["category"] for d in deltas],
            "delta_data": [d["delta"] for d in deltas],
            "sube_top": subidas[0] if subidas else None,
            "baja_top": bajadas[0] if bajadas else None,
            "dia_labels": list(range(1, dias_totales + 1)),
            "dia_data": por_dia(gastos_mes, dias_totales),
            "por_persona": por_persona(gastos_mes),
            "compartido": compartido_vs_no(gastos_mes),
            "por_metodo": por_metodo_pago(gastos_mes),
            "por_quincena": por_quincena(gastos_mes),
            "top10": top_gastos(gastos_mes, 10),
        },
    )


@router.get("/stats/anio", response_class=HTMLResponse)
def stats_anio(request: Request, anio: int | None = None):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    hoy = today_bogota()
    year = anio or hoy.year
    supa = get_supabase()

    gastos = cast(
        "list[dict[str, Any]]",
        supa.table("expenses")
        .select("category, amount, occurred_on")
        .gte("occurred_on", f"{year:04d}-01-01")
        .lte("occurred_on", f"{year:04d}-12-31")
        .execute()
        .data,
    )

    totales_mes = total_por_mes(gastos)
    meses_con_gasto = sum(1 for t in totales_mes if t > 0)

    return templates.TemplateResponse(
        request,
        "stats_anio.html",
        {
            "user": user,
            "active_tab": "stats",
            "anio_actual": year,
            "anio_anterior": year - 1,
            "anio_siguiente": year + 1,
            "anios_disponibles": sorted(_meses_por_ano().keys(), reverse=True),
            "meses_label": MESES,
            "total_anio": sum(totales_mes),
            "totales_mes": totales_mes,
            "promedio_categoria": promedio_mensual_por_categoria(gastos, meses_con_gasto),
        },
    )
