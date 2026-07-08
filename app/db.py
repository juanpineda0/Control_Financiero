"""Cliente de Supabase.

Usamos la SERVICE_ROLE key porque el codigo corre en el servidor (de confianza).
La base de datos es compartida por los dos usuarios (sin RLS, por diseno): el control de
acceso lo hace `auth.py` (login + lista blanca de correos).
"""
from functools import lru_cache

import httpx
from supabase import Client, ClientOptions, create_client

from .config import settings


@lru_cache
def get_supabase() -> Client:
    # http2=False: por defecto supabase-py fuerza HTTP/2, que en Windows puede fallar
    # de forma intermitente al reusar una conexion keep-alive con
    # "httpx.ReadError: [WinError 10035]" (bug conocido de httpx/httpcore en Windows).
    # HTTP/1.1 evita ese problema; el rendimiento no importa aqui (una app personal).
    http_client = httpx.Client(http2=False)
    options = ClientOptions(httpx_client=http_client)
    return create_client(
        settings.supabase_url, settings.supabase_service_role_key, options=options
    )
