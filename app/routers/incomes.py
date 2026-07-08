"""Rutas de ingresos: formulario, lista mensual, editar y borrar."""
from typing import Any, cast

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import auth
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
from ..services.settlement import totales_por_persona
from ..templating import templates

router = APIRouter()

INCOME_KINDS: list[str] = ["Sueldo", "Extra"]


def _clean_kind(kind: str) -> str:
    return kind if kind in INCOME_KINDS else INCOME_KINDS[0]


def _redirect_to_month(mes: str | None) -> RedirectResponse:
    destino = f"/ingresos?mes={mes}" if mes else "/ingresos"
    return RedirectResponse(destino, status_code=303)


def personas_registradas(nombre_sesion: str) -> list[str]:
    """Nombres distintos vistos en gastos e ingresos (los dos de la pareja),
    incluyendo siempre al usuario de la sesion.
    """
    supa = get_supabase()
    nombres: set[str] = {nombre_sesion}
    for tabla in ("expenses", "incomes"):
        filas = cast(
            "list[dict[str, Any]]",
            supa.table(tabla).select("user_name").execute().data,
        )
        nombres.update(f["user_name"] for f in filas)
    return sorted(nombres)


def _meses_por_ano() -> dict[int, list[int]]:
    fechas = cast(
        "list[dict[str, Any]]",
        get_supabase().table("incomes").select("occurred_on").execute().data,
    )
    return meses_con_datos([f["occurred_on"] for f in fechas])


@router.get("/ingresos", response_class=HTMLResponse)
def ingresos_list(request: Request, mes: str | None = None):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    year, month = parse_month_param(mes)
    start, end = month_bounds(year, month)
    hoy = today_bogota()

    ingresos = cast(
        "list[dict[str, Any]]",
        get_supabase()
        .table("incomes")
        .select("*")
        .gte("occurred_on", start.isoformat())
        .lte("occurred_on", end.isoformat())
        .order("occurred_on", desc=True)
        .order("created_at", desc=True)
        .execute()
        .data,
    )
    totales = totales_por_persona(ingresos)

    return templates.TemplateResponse(
        request,
        "ingresos.html",
        {
            "user": user,
            "active_tab": "ingresos",
            "income_kinds": INCOME_KINDS,
            "personas": personas_registradas(user["name"]),
            "today": hoy.isoformat(),
            "ingresos": ingresos,
            "total_mes": sum(totales.values()),
            "totales_por_persona": totales,
            "base_path": "/ingresos",
            "mes_actual": f"{year:04d}-{month:02d}",
            "mes_label": month_label(year, month),
            "mes_anterior": shift_month(year, month, -1),
            "mes_siguiente": shift_month(year, month, 1),
            "meses_por_ano": _meses_por_ano(),
            "meses_cortos": MESES_CORTOS,
        },
    )


@router.post("/ingresos")
def crear_ingreso(
    request: Request,
    occurred_on: str = Form(...),
    amount: int = Form(..., gt=0),
    kind: str = Form(INCOME_KINDS[0]),
    description: str = Form(""),
    user_name: str = Form(""),
    mes: str | None = Form(None),
):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    get_supabase().table("incomes").insert(
        {
            "occurred_on": occurred_on,
            "amount": amount,
            "kind": _clean_kind(kind),
            "description": description.strip() or None,
            "user_name": user_name.strip() or user["name"],
        }
    ).execute()
    return _redirect_to_month(mes)


@router.get("/ingresos/{income_id}/editar", response_class=HTMLResponse)
def editar_ingreso_form(request: Request, income_id: str, mes: str | None = None):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    ingreso = (
        get_supabase()
        .table("incomes")
        .select("*")
        .eq("id", income_id)
        .single()
        .execute()
        .data
    )
    return templates.TemplateResponse(
        request,
        "ingresos_editar.html",
        {
            "user": user,
            "active_tab": "ingresos",
            "income_kinds": INCOME_KINDS,
            "personas": personas_registradas(user["name"]),
            "ingreso": ingreso,
            "mes": mes or "",
        },
    )


@router.post("/ingresos/{income_id}/editar")
def editar_ingreso(
    request: Request,
    income_id: str,
    occurred_on: str = Form(...),
    amount: int = Form(..., gt=0),
    kind: str = Form(INCOME_KINDS[0]),
    description: str = Form(""),
    user_name: str = Form(""),
    mes: str | None = Form(None),
):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    get_supabase().table("incomes").update(
        {
            "occurred_on": occurred_on,
            "amount": amount,
            "kind": _clean_kind(kind),
            "description": description.strip() or None,
            "user_name": user_name.strip() or user["name"],
        }
    ).eq("id", income_id).execute()
    return _redirect_to_month(mes)


@router.post("/ingresos/{income_id}/eliminar")
def eliminar_ingreso(request: Request, income_id: str, mes: str | None = Form(None)):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    get_supabase().table("incomes").delete().eq("id", income_id).execute()
    return _redirect_to_month(mes)
