"""Autenticacion con Google via Supabase (OAuth + PKCE) y sesion por cookie firmada.

Flujo:
  1) /auth/start  -> generamos un par PKCE (verifier + challenge), guardamos el verifier
     en una cookie corta y firmada, y mandamos al usuario a Supabase/Google.
  2) Supabase/Google devuelven a /auth/callback?code=...
  3) Intercambiamos el `code` + `verifier` por los datos del usuario (email, nombre).
  4) Validamos contra la lista blanca de correos y guardamos una sesion en cookie firmada
     de ~30 dias (asi no toca volver a iniciar sesion seguido).

Nota: la sesion es una cookie firmada de 30 dias (suficiente para "no reloguear tan
seguido"). No guardamos el token de Supabase porque el acceso a datos usa la service-role
key y la base es compartida sin RLS (por diseno). Solo usamos Google para identificar
quien entra y validarlo contra la lista blanca.
"""
import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import settings

SESSION_COOKIE = "fin_session"
PKCE_COOKIE = "fin_pkce"
SESSION_MAX_AGE = 30 * 24 * 3600  # 30 dias
PKCE_MAX_AGE = 600  # 10 minutos para completar el login

_serializer = URLSafeTimedSerializer(settings.session_secret)
# En produccion (https) la cookie va como Secure; en local (http) no, o el navegador la descarta.
_secure = settings.base_url.lower().startswith("https")


# ---------------------------------------------------------------- PKCE
def generate_pkce() -> tuple[str, str]:
    """Devuelve (code_verifier, code_challenge) para el flujo PKCE."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def build_authorize_url(challenge: str) -> str:
    params = {
        "provider": "google",
        "redirect_to": f"{settings.base_url}/auth/callback",
        "code_challenge": challenge,
        "code_challenge_method": "s256",
    }
    return f"{settings.supabase_url}/auth/v1/authorize?{urlencode(params)}"


def set_pkce_cookie(response: Response, verifier: str) -> None:
    response.set_cookie(
        PKCE_COOKIE,
        _serializer.dumps(verifier),
        max_age=PKCE_MAX_AGE,
        httponly=True,
        secure=_secure,
        samesite="lax",
        path="/",
    )


def read_pkce(request: Request) -> str | None:
    raw = request.cookies.get(PKCE_COOKIE)
    if not raw:
        return None
    try:
        return _serializer.loads(raw, max_age=PKCE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


async def exchange_code(code: str, verifier: str) -> dict:
    """Cambia el `code` por la sesion en Supabase (devuelve el JSON con `user`)."""
    url = f"{settings.supabase_url}/auth/v1/token?grant_type=pkce"
    headers = {
        "apikey": settings.supabase_anon_key,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url, headers=headers, json={"auth_code": code, "code_verifier": verifier}
        )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------- Sesion
def set_session(response: Response, email: str, name: str) -> None:
    payload = {"email": email.lower(), "name": name}
    response.set_cookie(
        SESSION_COOKIE,
        _serializer.dumps(payload),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=_secure,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(PKCE_COOKIE, path="/")


def get_session(request: Request) -> dict | None:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    try:
        return _serializer.loads(raw, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


# ---------------------------------------------------------------- Lista blanca
def is_allowed(email: str) -> bool:
    """Solo dejan entrar los correos configurados en ALLOWED_EMAILS.

    Si la lista esta vacia, negamos por seguridad (fail-closed).
    """
    allowed = settings.allowed_emails_list
    return bool(allowed) and email.lower() in allowed
