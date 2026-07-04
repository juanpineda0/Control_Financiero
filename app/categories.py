"""Listas para los desplegables del formulario de gastos.

Por ahora son constantes (faciles de editar). Mas adelante podemos moverlas a una tabla
en la base de datos para editarlas sin tocar el codigo.
"""

CATEGORIES: list[str] = [
    "Mercado",
    "Comida fuera",
    "Transporte",
    "Servicios",
    "Mecato",
    "Cuota Casa",
    "Suscripciones",
    "Salud",
    "Entretenimiento",
    "Ropa",
    "Mascotas",
    "Hogar",
    "Otros",
]

# El primero es el metodo por defecto en el formulario.
PAYMENT_METHODS: list[str] = ["Efectivo", "T. Debito", "T. Credito"]
