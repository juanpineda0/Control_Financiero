"""Rutas del settle-up mensual (/cuentas): quien le debe cuanto a quien por los
gastos compartidos, transferencias entre los dos y cierre del mes (saldar).
"""
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
from ..services.settlement import (
    cuotas_justas,
    deuda,
    pct_ahorro,
    proporciones,
    saldos,
    totales_por_persona,
)
from ..templating import templates
from .incomes import personas_registradas

router = APIRouter()


def _redirect_to_month(mes: str | None) -> RedirectResponse:
    destino = f"/cuentas?mes={mes}" if mes else "/cuentas"
    return RedirectResponse(destino, status_code=303)


def _meses_por_ano() -> dict[int, list[int]]:
    fechas = cast(
        "list[dict[str, Any]]",
        get_supabase().table("expenses").select("occurred_on").execute().data,
    )
    return meses_con_datos([f["occurred_on"] for f in fechas])


def _rango(tabla: str, start, end, columnas: str = "*") -> list[dict[str, Any]]:
    return cast(
        "list[dict[str, Any]]",
        get_supabase()
        .table(tabla)
        .select(columnas)
        .gte("occurred_on", start.isoformat())
        .lte("occurred_on", end.isoformat())
        .order("occurred_on", desc=True)
        .order("created_at", desc=True)
        .execute()
        .data,
    )


def ingresos_para_proporcion(year: int, month: int) -> tuple[list[dict[str, Any]], str | None]:
    """Ingresos con los que se calcula la proporcion del mes. Si el mes no tiene,
    usa el ultimo mes anterior que si tenga; devuelve (ingresos, label del mes
    usado o None si es el mismo).
    """
    start, end = month_bounds(year, month)
    ingresos = _rango("incomes", start, end)
    if ingresos:
        return ingresos, None

    anterior = cast(
        "list[dict[str, Any]]",
        get_supabase()
        .table("incomes")
        .select("occurred_on")
        .lt("occurred_on", start.isoformat())
        .order("occurred_on", desc=True)
        .limit(1)
        .execute()
        .data,
    )
    if not anterior:
        return [], None
    f = anterior[0]["occurred_on"]
    y, m = int(f[:4]), int(f[5:7])
    return _rango("incomes", *month_bounds(y, m)), month_label(y, m)


def _datos_cuentas(year: int, month: int) -> dict[str, Any]:
    """Trae los datos del mes y calcula el settle-up completo."""
    start, end = month_bounds(year, month)

    gastos = _rango("expenses", start, end, "amount, user_name, is_shared")
    compartidos = [g for g in gastos if g["is_shared"]]
    total_gastos = sum(int(g["amount"]) for g in gastos)
    total_compartido = sum(int(g["amount"]) for g in compartidos)

    ingresos_mes = _rango("incomes", start, end)
    ingresos_prop, mes_proporcion = ingresos_para_proporcion(year, month)
    ingresos_por_persona = totales_por_persona(ingresos_prop)
    props = proporciones(ingresos_por_persona)

    transferencias = _rango("transfers", start, end)
    enviado = totales_por_persona(transferencias, "from_user")
    recibido = totales_por_persona(transferencias, "to_user")
    pagado = totales_por_persona(compartidos)

    cuotas = cuotas_justas(total_compartido, props)
    saldos_mes = saldos(cuotas, pagado, enviado, recibido) if props else {}

    saldado = cast(
        "list[dict[str, Any]]",
        get_supabase()
        .table("settlements")
        .select("*")
        .eq("month", start.isoformat())
        .execute()
        .data,
    )

    personas = sorted(set(props) | set(pagado) | set(enviado) | set(recibido))
    filas = [
        {
            "persona": p,
            "proporcion": props.get(p),
            "ingreso": ingresos_por_persona.get(p, 0),
            "cuota": cuotas.get(p, 0),
            "pagado": pagado.get(p, 0),
            "transferido": enviado.get(p, 0) - recibido.get(p, 0),
            "saldo": saldos_mes.get(p, 0),
        }
        for p in personas
    ]

    return {
        "total_gastos": total_gastos,
        "total_compartido": total_compartido,
        "total_ingresos": sum(int(i["amount"]) for i in ingresos_mes),
        "mes_proporcion": mes_proporcion,
        "sin_proporcion": not props,
        "filas": filas,
        "deuda": deuda(saldos_mes),
        "pct_ahorro": pct_ahorro(sum(int(i["amount"]) for i in ingresos_mes), total_gastos),
        "transferencias": transferencias,
        "saldado": saldado[0] if saldado else None,
    }


@router.get("/cuentas", response_class=HTMLResponse)
def cuentas(request: Request, mes: str | None = None):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    year, month = parse_month_param(mes)
    datos = _datos_cuentas(year, month)
    personas = personas_registradas(user["name"])
    # direccion por defecto del pase rapido: el otro -> quien esta usando la app
    otro = next((p for p in personas if p != user["name"]), user["name"])

    return templates.TemplateResponse(
        request,
        "cuentas.html",
        {
            "user": user,
            "active_tab": "cuentas",
            "personas": personas,
            "otro": otro,
            "today": today_bogota().isoformat(),
            **datos,
            "base_path": "/cuentas",
            "mes_actual": f"{year:04d}-{month:02d}",
            "mes_label": month_label(year, month),
            "mes_anterior": shift_month(year, month, -1),
            "mes_siguiente": shift_month(year, month, 1),
            "meses_por_ano": _meses_por_ano(),
            "meses_cortos": MESES_CORTOS,
        },
    )


@router.post("/cuentas/transferencias")
def crear_transferencia(
    request: Request,
    occurred_on: str = Form(...),
    amount: int = Form(..., gt=0),
    from_user: str = Form(...),
    to_user: str = Form(...),
    note: str = Form(""),
    mes: str | None = Form(None),
):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    if from_user != to_user:
        get_supabase().table("transfers").insert(
            {
                "occurred_on": occurred_on,
                "amount": amount,
                "from_user": from_user,
                "to_user": to_user,
                "note": note.strip() or None,
            }
        ).execute()
    return _redirect_to_month(mes)


@router.post("/cuentas/transferencias/{transfer_id}/eliminar")
def eliminar_transferencia(
    request: Request, transfer_id: str, mes: str | None = Form(None)
):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    get_supabase().table("transfers").delete().eq("id", transfer_id).execute()
    return _redirect_to_month(mes)


@router.post("/cuentas/saldar")
def saldar_mes(request: Request, mes: str | None = Form(None)):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    year, month = parse_month_param(mes)
    start, _ = month_bounds(year, month)
    datos = _datos_cuentas(year, month)

    # la deuda se recalcula en el servidor: no se confia en montos del form
    if not datos["saldado"] and not datos["sin_proporcion"]:
        personas = sorted(f["persona"] for f in datos["filas"])
        if datos["deuda"]:
            deudor, acreedor, monto = datos["deuda"]
        elif len(personas) >= 2:
            deudor, acreedor, monto = personas[0], personas[1], 0  # paz y salvo
        else:
            return _redirect_to_month(mes)
        get_supabase().table("settlements").insert(
            {
                "month": start.isoformat(),
                "from_user": deudor,
                "to_user": acreedor,
                "amount": monto,
            }
        ).execute()
    return _redirect_to_month(mes)


@router.post("/cuentas/deshacer")
def deshacer_saldado(request: Request, mes: str | None = Form(None)):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    year, month = parse_month_param(mes)
    start, _ = month_bounds(year, month)
    get_supabase().table("settlements").delete().eq("month", start.isoformat()).execute()
    return _redirect_to_month(mes)
