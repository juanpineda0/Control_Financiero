"""Cliente de Supabase.

Usamos la SERVICE_ROLE key porque el codigo corre en el servidor (de confianza).
La base de datos es compartida por los dos usuarios (sin RLS, por diseno): el control de
acceso lo hace `auth.py` (login + lista blanca de correos).
"""
from functools import lru_cache

from supabase import Client, create_client

from .config import settings


@lru_cache
def get_supabase() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
