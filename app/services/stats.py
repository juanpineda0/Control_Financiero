"""Calculos puros para estadisticas: reciben listas de gastos ya traidas de Supabase
(sin tocar la base de datos) y devuelven agregados listos para las plantillas.
"""
from datetime import date
from typing import Any

from ..categories import PAYMENT_METHODS


def total_gastado(gastos: list[dict[str, Any]]) -> int:
    return sum(int(g["amount"]) for g in gastos)


def por_categoria(gastos: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """Categorias con gasto > 0, de mayor a menor."""
    totales: dict[str, int] = {}
    for g in gastos:
        cat = g["category"]
        totales[cat] = totales.get(cat, 0) + int(g["amount"])
    return sorted(totales.items(), key=lambda item: item[1], reverse=True)


def por_dia(gastos: list[dict[str, Any]], dias_totales: int) -> list[int]:
    """Lista de largo `dias_totales`, indice 0 = dia 1 del mes."""
    totales = [0] * dias_totales
    for g in gastos:
        dia = int(g["occurred_on"][8:10])
        if 1 <= dia <= dias_totales:
            totales[dia - 1] += int(g["amount"])
    return totales


def delta_por_categoria(
    actual: list[tuple[str, int]], anterior: list[tuple[str, int]]
) -> list[dict[str, Any]]:
    """Delta (actual - anterior) por categoria con movimiento en cualquiera de los dos
    meses, ordenado por magnitud del cambio (de mayor a menor)."""
    actual_map = dict(actual)
    anterior_map = dict(anterior)
    categorias = set(actual_map) | set(anterior_map)
    filas = [
        {
            "category": cat,
            "actual": actual_map.get(cat, 0),
            "anterior": anterior_map.get(cat, 0),
            "delta": actual_map.get(cat, 0) - anterior_map.get(cat, 0),
        }
        for cat in categorias
    ]
    filas.sort(key=lambda f: abs(f["delta"]), reverse=True)
    return filas


def por_persona(gastos: list[dict[str, Any]]) -> list[tuple[str, int]]:
    totales: dict[str, int] = {}
    for g in gastos:
        nombre = g["user_name"]
        totales[nombre] = totales.get(nombre, 0) + int(g["amount"])
    return sorted(totales.items(), key=lambda item: item[1], reverse=True)


def compartido_vs_no(gastos: list[dict[str, Any]]) -> list[tuple[str, int]]:
    compartido = sum(int(g["amount"]) for g in gastos if g["is_shared"])
    no_compartido = sum(int(g["amount"]) for g in gastos if not g["is_shared"])
    return [("Compartido", compartido), ("No compartido", no_compartido)]


def por_metodo_pago(gastos: list[dict[str, Any]]) -> list[tuple[str, int]]:
    totales = {m: 0 for m in PAYMENT_METHODS}
    for g in gastos:
        metodo = g["payment_method"]
        totales[metodo] = totales.get(metodo, 0) + int(g["amount"])
    return [(m, totales[m]) for m in PAYMENT_METHODS]


def por_quincena(gastos: list[dict[str, Any]]) -> list[tuple[str, int]]:
    primera = sum(int(g["amount"]) for g in gastos if int(g["occurred_on"][8:10]) <= 15)
    segunda = sum(int(g["amount"]) for g in gastos if int(g["occurred_on"][8:10]) > 15)
    return [("Del 1 al 15", primera), ("Del 16 al fin", segunda)]


def dias_transcurridos_mes(hoy: date, year: int, month: int, dias_totales: int) -> int:
    """Dias ya transcurridos del mes mostrado (para promedio diario y proyeccion)."""
    if (year, month) < (hoy.year, hoy.month):
        return dias_totales
    if (year, month) == (hoy.year, hoy.month):
        return hoy.day
    return 0


def promedio_diario(total: int, dias_transcurridos: int) -> float:
    if dias_transcurridos <= 0:
        return 0.0
    return total / dias_transcurridos


def proyeccion_cierre(total: int, dias_transcurridos: int, dias_totales: int) -> int | None:
    """Al ritmo actual, total proyectado a fin de mes. None si el mes no esta en curso
    (ya termino, o todavia no empieza)."""
    if dias_transcurridos <= 0 or dias_transcurridos >= dias_totales:
        return None
    return round(total / dias_transcurridos * dias_totales)


def top_gastos(gastos: list[dict[str, Any]], n: int = 10) -> list[dict[str, Any]]:
    return sorted(gastos, key=lambda g: int(g["amount"]), reverse=True)[:n]


def total_por_mes(gastos_del_ano: list[dict[str, Any]]) -> list[int]:
    """Lista de largo 12, indice 0 = enero."""
    totales = [0] * 12
    for g in gastos_del_ano:
        mes = int(g["occurred_on"][5:7])
        totales[mes - 1] += int(g["amount"])
    return totales


def promedio_mensual_por_categoria(
    gastos_del_ano: list[dict[str, Any]], meses_con_datos: int
) -> list[tuple[str, float]]:
    """Promedio mensual por categoria (solo las que tienen gasto), de mayor a menor."""
    if meses_con_datos <= 0:
        return []
    totales: dict[str, int] = {}
    for g in gastos_del_ano:
        cat = g["category"]
        totales[cat] = totales.get(cat, 0) + int(g["amount"])
    promedios = [(cat, total / meses_con_datos) for cat, total in totales.items()]
    return sorted(promedios, key=lambda item: item[1], reverse=True)
