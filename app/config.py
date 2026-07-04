"""Configuracion de la app, leida desde variables de entorno (.env en local)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Sesion / seguridad
    session_secret: str
    # Correos permitidos (solo ustedes dos), separados por coma
    allowed_emails: str = ""

    # URL base de la app (cambia en produccion a la URL de Vercel)
    base_url: str = "http://localhost:8000"

    @property
    def allowed_emails_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_emails.split(",") if e.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings() # type: ignore[call-arg]


settings = get_settings()
