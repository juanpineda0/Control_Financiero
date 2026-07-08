"""Calculos puros del settle-up mensual: proporcion por ingresos, cuota justa de
los gastos compartidos y saldo de cada persona. Reciben dicts ya traidos de
Supabase y no tocan la base de datos.
"""
from typing import Any


def totales_por_persona(
    filas: list[dict[str, Any]], campo_persona: str = "user_name"
) -> dict[str, int]:
    resultado: dict[str, int] = {}
    for f in filas:
        persona = f[campo_persona]
        resultado[persona] = resultado.get(persona, 0) + int(f["amount"])
    return resultado


def proporciones(ingresos_por_persona: dict[str, int]) -> dict[str, float]:
    """Parte del total que aporta cada persona (0..1). Vacio si no hay ingresos."""
    total = sum(ingresos_por_persona.values())
    if total <= 0:
        return {}
    return {p: v / total for p, v in ingresos_por_persona.items()}


def cuotas_justas(total_compartido: int, props: dict[str, float]) -> dict[str, int]:
    """Reparte el total compartido segun las proporciones, en enteros que suman
    exacto el total (la ultima persona absorbe el ajuste de redondeo).
    """
    personas = list(props)
    cuotas: dict[str, int] = {}
    repartido = 0
    for p in personas[:-1]:
        cuotas[p] = round(total_compartido * props[p])
        repartido += cuotas[p]
    if personas:
        cuotas[personas[-1]] = total_compartido - repartido
    return cuotas


def saldos(
    cuotas: dict[str, int],
    pagado: dict[str, int],
    enviado: dict[str, int],
    recibido: dict[str, int],
) -> dict[str, int]:
    """Saldo de cada persona: lo que pago en gastos compartidos mas lo que
    transfirio, menos lo que recibio y su cuota justa. Positivo = puso de mas
    (le deben); negativo = debe.
    """
    personas = set(cuotas) | set(pagado) | set(enviado) | set(recibido)
    return {
        p: pagado.get(p, 0) + enviado.get(p, 0) - recibido.get(p, 0) - cuotas.get(p, 0)
        for p in personas
    }


def deuda(saldos_mes: dict[str, int]) -> tuple[str, str, int] | None:
    """(deudor, acreedor, monto) o None si estan a paz y salvo.

    Pensado para dos personas: el de saldo negativo le debe al de saldo positivo
    (los saldos siempre suman cero).
    """
    if len(saldos_mes) < 2:
        return None
    deudor = min(saldos_mes, key=lambda p: saldos_mes[p])
    acreedor = max(saldos_mes, key=lambda p: saldos_mes[p])
    monto = min(-saldos_mes[deudor], saldos_mes[acreedor])
    if monto <= 0:
        return None
    return deudor, acreedor, monto


def pct_ahorro(total_ingresos: int, total_gastos: int) -> float | None:
    """% de ahorro del mes = (ingresos - gastos) / ingresos. None sin ingresos."""
    if total_ingresos <= 0:
        return None
    return (total_ingresos - total_gastos) / total_ingresos * 100
