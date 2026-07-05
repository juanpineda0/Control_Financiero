"""Rutas de ahorros: metas de ahorro/deuda, aportes/retiros, editar/archivar/borrar."""
from datetime import date
from typing import Any, cast

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import auth
from ..dates import today_bogota
from ..db import get_supabase
from ..services.savings import (
    cuota_sugerida,
    desglose_por_persona,
    esperado_a_hoy,
    estado_meta,
    fecha_estimada_pago,
    progreso_pct,
    ritmo_mensual_deuda,
    total_ahorrado,
)
from ..templating import templates

router = APIRouter()

GOAL_KINDS: list[str] = ["ahorro", "deuda"]


def _clean_kind(kind: str) -> str:
    return kind if kind in GOAL_KINDS else GOAL_KINDS[0]


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _calcular_progreso(
    meta: dict[str, Any], contribuciones: list[dict[str, Any]], hoy: date
) -> dict[str, Any]:
    ahorrado = total_ahorrado(contribuciones)
    target_amount = int(meta["target_amount"])
    target_date = _parse_date(meta.get("target_date"))
    created_at = date.fromisoformat(meta["created_at"][:10])
    restante = max(target_amount - ahorrado, 0)

    resultado: dict[str, Any] = {
        "ahorrado": ahorrado,
        "restante": restante,
        "progreso": progreso_pct(ahorrado, target_amount),
        "desglose": desglose_por_persona(contribuciones),
        "cuota_sugerida": None,
        "ritmo_mensual": None,
        "fecha_estimada": None,
        "estado": None,
    }
    if meta["kind"] == "deuda":
        resultado["ritmo_mensual"] = ritmo_mensual_deuda(contribuciones, hoy)
        resultado["fecha_estimada"] = fecha_estimada_pago(restante, resultado["ritmo_mensual"], hoy)
        if ahorrado >= target_amount:
            resultado["estado"] = "cumplida"
    else:
        esperado = esperado_a_hoy(target_amount, created_at, target_date, hoy)
        resultado["cuota_sugerida"] = cuota_sugerida(ahorrado, target_amount, hoy, target_date)
        resultado["estado"] = estado_meta(ahorrado, target_amount, esperado)
    return resultado


@router.get("/ahorros", response_class=HTMLResponse)
def ahorros_list(request: Request):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    hoy = today_bogota()
    supa = get_supabase()

    metas = cast(
        "list[dict[str, Any]]",
        supa.table("savings_goals")
        .select("*")
        .eq("is_archived", False)
        .order("created_at")
        .execute()
        .data,
    )
    archivadas = cast(
        "list[dict[str, Any]]",
        supa.table("savings_goals")
        .select("*")
        .eq("is_archived", True)
        .order("created_at")
        .execute()
        .data,
    )

    goal_ids = [m["id"] for m in metas]
    aportes_por_meta: dict[str, list[dict[str, Any]]] = {gid: [] for gid in goal_ids}
    if goal_ids:
        aportes = cast(
            "list[dict[str, Any]]",
            supa.table("savings_contributions")
            .select("*")
            .in_("goal_id", goal_ids)
            .execute()
            .data,
        )
        for a in aportes:
            aportes_por_meta.setdefault(a["goal_id"], []).append(a)

    tarjetas = [
        {"meta": meta, **_calcular_progreso(meta, aportes_por_meta.get(meta["id"], []), hoy)}
        for meta in metas
    ]

    return templates.TemplateResponse(
        request,
        "ahorros.html",
        {
            "user": user,
            "active_tab": "ahorros",
            "goal_kinds": GOAL_KINDS,
            "today": hoy.isoformat(),
            "tarjetas": tarjetas,
            "archivadas": archivadas,
        },
    )


@router.post("/ahorros/nueva")
def crear_meta(
    request: Request,
    name: str = Form(...),
    kind: str = Form(GOAL_KINDS[0]),
    target_amount: int = Form(..., gt=0),
    target_date: str = Form(""),
    emoji: str = Form(""),
):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    get_supabase().table("savings_goals").insert(
        {
            "name": name.strip(),
            "kind": _clean_kind(kind),
            "target_amount": target_amount,
            "target_date": target_date or None,
            "emoji": emoji.strip() or None,
        }
    ).execute()
    return RedirectResponse("/ahorros", status_code=303)


@router.get("/ahorros/{goal_id}", response_class=HTMLResponse)
def meta_detalle(request: Request, goal_id: str):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    hoy = today_bogota()
    supa = get_supabase()
    meta = cast(
        "dict[str, Any]",
        supa.table("savings_goals").select("*").eq("id", goal_id).single().execute().data,
    )
    aportes = cast(
        "list[dict[str, Any]]",
        supa.table("savings_contributions")
        .select("*")
        .eq("goal_id", goal_id)
        .order("occurred_on", desc=True)
        .order("created_at", desc=True)
        .execute()
        .data,
    )

    return templates.TemplateResponse(
        request,
        "ahorros_detalle.html",
        {
            "user": user,
            "active_tab": "ahorros",
            "meta": meta,
            "aportes": aportes,
            "today": hoy.isoformat(),
            "puede_borrar": len(aportes) == 0,
            **_calcular_progreso(meta, aportes, hoy),
        },
    )


@router.post("/ahorros/{goal_id}/aportes")
def crear_aporte(
    request: Request,
    goal_id: str,
    tipo: str = Form(...),
    occurred_on: str = Form(...),
    amount: int = Form(..., gt=0),
    note: str = Form(""),
):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    monto = amount if tipo == "aporte" else -amount
    get_supabase().table("savings_contributions").insert(
        {
            "goal_id": goal_id,
            "amount": monto,
            "occurred_on": occurred_on,
            "user_name": user["name"],
            "note": note.strip() or None,
        }
    ).execute()
    return RedirectResponse(f"/ahorros/{goal_id}", status_code=303)


@router.get("/ahorros/{goal_id}/editar", response_class=HTMLResponse)
def editar_meta_form(request: Request, goal_id: str):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    meta = cast(
        "dict[str, Any]",
        get_supabase().table("savings_goals").select("*").eq("id", goal_id).single().execute().data,
    )
    return templates.TemplateResponse(
        request,
        "ahorros_editar.html",
        {"user": user, "active_tab": "ahorros", "goal_kinds": GOAL_KINDS, "meta": meta},
    )


@router.post("/ahorros/{goal_id}/editar")
def editar_meta(
    request: Request,
    goal_id: str,
    name: str = Form(...),
    kind: str = Form(GOAL_KINDS[0]),
    target_amount: int = Form(..., gt=0),
    target_date: str = Form(""),
    emoji: str = Form(""),
):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    get_supabase().table("savings_goals").update(
        {
            "name": name.strip(),
            "kind": _clean_kind(kind),
            "target_amount": target_amount,
            "target_date": target_date or None,
            "emoji": emoji.strip() or None,
        }
    ).eq("id", goal_id).execute()
    return RedirectResponse(f"/ahorros/{goal_id}", status_code=303)


@router.post("/ahorros/{goal_id}/archivar")
def archivar_meta(request: Request, goal_id: str):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    get_supabase().table("savings_goals").update({"is_archived": True}).eq("id", goal_id).execute()
    return RedirectResponse("/ahorros", status_code=303)


@router.post("/ahorros/{goal_id}/reactivar")
def reactivar_meta(request: Request, goal_id: str):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    get_supabase().table("savings_goals").update({"is_archived": False}).eq("id", goal_id).execute()
    return RedirectResponse("/ahorros", status_code=303)


@router.post("/ahorros/{goal_id}/borrar")
def borrar_meta(request: Request, goal_id: str):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    tiene_aportes = (
        get_supabase()
        .table("savings_contributions")
        .select("id")
        .eq("goal_id", goal_id)
        .limit(1)
        .execute()
        .data
    )
    if not tiene_aportes:
        get_supabase().table("savings_goals").delete().eq("id", goal_id).execute()
    return RedirectResponse("/ahorros", status_code=303)
