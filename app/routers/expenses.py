"""Rutas de gastos: formulario, lista mensual, editar y borrar."""
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import auth
from ..categories import CATEGORIES, PAYMENT_METHODS
from ..dates import month_bounds, month_label, parse_month_param, shift_month, today_bogota
from ..db import get_supabase
from ..templating import templates

router = APIRouter()


def _clean_category(category: str) -> str:
    return category if category in CATEGORIES else "Otros"


def _clean_payment_method(payment_method: str) -> str:
    return payment_method if payment_method in PAYMENT_METHODS else PAYMENT_METHODS[0]


def _redirect_to_month(mes: str | None) -> RedirectResponse:
    destino = f"/?mes={mes}" if mes else "/"
    return RedirectResponse(destino, status_code=303)


@router.get("/", response_class=HTMLResponse)
def index(request: Request, mes: str | None = None):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    year, month = parse_month_param(mes)
    start, end = month_bounds(year, month)

    gastos = (
        get_supabase()
        .table("expenses")
        .select("*")
        .gte("occurred_on", start.isoformat())
        .lte("occurred_on", end.isoformat())
        .order("occurred_on", desc=True)
        .order("created_at", desc=True)
        .execute()
        .data
    )
    total_mes = sum(g["amount"] for g in gastos)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "user": user,
            "categories": CATEGORIES,
            "payment_methods": PAYMENT_METHODS,
            "today": today_bogota().isoformat(),
            "expenses": gastos,
            "total_mes": total_mes,
            "mes_actual": f"{year:04d}-{month:02d}",
            "mes_label": month_label(year, month),
            "mes_anterior": shift_month(year, month, -1),
            "mes_siguiente": shift_month(year, month, 1),
        },
    )


@router.post("/expenses")
def create_expense(
    request: Request,
    occurred_on: str = Form(...),
    amount: int = Form(..., gt=0),
    category: str = Form(...),
    description: str = Form(""),
    payment_method: str = Form(PAYMENT_METHODS[0]),
    is_shared: bool = Form(False),
    mes: str | None = Form(None),
):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    get_supabase().table("expenses").insert(
        {
            "occurred_on": occurred_on,
            "amount": amount,
            "description": description.strip() or None,
            "category": _clean_category(category),
            "payment_method": _clean_payment_method(payment_method),
            "user_name": user["name"],
            "is_shared": is_shared,
        }
    ).execute()
    return _redirect_to_month(mes)


@router.get("/expenses/{expense_id}/editar", response_class=HTMLResponse)
def edit_expense_form(request: Request, expense_id: str, mes: str | None = None):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    gasto = (
        get_supabase()
        .table("expenses")
        .select("*")
        .eq("id", expense_id)
        .single()
        .execute()
        .data
    )
    return templates.TemplateResponse(
        request,
        "edit_expense.html",
        {
            "user": user,
            "categories": CATEGORIES,
            "payment_methods": PAYMENT_METHODS,
            "expense": gasto,
            "mes": mes or "",
        },
    )


@router.post("/expenses/{expense_id}/editar")
def update_expense(
    request: Request,
    expense_id: str,
    occurred_on: str = Form(...),
    amount: int = Form(..., gt=0),
    category: str = Form(...),
    description: str = Form(""),
    payment_method: str = Form(PAYMENT_METHODS[0]),
    is_shared: bool = Form(False),
    mes: str | None = Form(None),
):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    get_supabase().table("expenses").update(
        {
            "occurred_on": occurred_on,
            "amount": amount,
            "description": description.strip() or None,
            "category": _clean_category(category),
            "payment_method": _clean_payment_method(payment_method),
            "is_shared": is_shared,
        }
    ).eq("id", expense_id).execute()
    return _redirect_to_month(mes)


@router.post("/expenses/{expense_id}/eliminar")
def delete_expense(request: Request, expense_id: str, mes: str | None = Form(None)):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    get_supabase().table("expenses").delete().eq("id", expense_id).execute()
    return _redirect_to_month(mes)
