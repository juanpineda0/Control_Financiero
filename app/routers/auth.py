"""Rutas de login: inicio de sesion con Google (PKCE via Supabase), callback y logout."""
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import auth
from ..templating import templates

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str | None = None):
    if auth.get_session(request):
        return RedirectResponse("/", status_code=303)
    mensajes = {
        "denied": "Ese correo no esta autorizado para usar la app.",
        "expired": "El intento de login expiro. Proba de nuevo.",
        "oauth": "No se pudo iniciar sesion con Google. Proba de nuevo.",
        "exchange": "Hubo un problema validando tu sesion. Proba de nuevo.",
    }
    return templates.TemplateResponse(
        request, "login.html", {"error": mensajes.get(error)}
    )


@router.get("/auth/start")
def auth_start():
    """Genera PKCE y redirige a Google (via Supabase)."""
    verifier, challenge = auth.generate_pkce()
    resp = RedirectResponse(auth.build_authorize_url(challenge), status_code=303)
    auth.set_pkce_cookie(resp, verifier)
    return resp


@router.get("/auth/callback")
async def auth_callback(request: Request, code: str | None = None, error: str | None = None):
    if error or not code:
        return RedirectResponse("/login?error=oauth", status_code=303)

    verifier = auth.read_pkce(request)
    if not verifier:
        return RedirectResponse("/login?error=expired", status_code=303)

    try:
        token = await auth.exchange_code(code, verifier)
    except httpx.HTTPError:
        return RedirectResponse("/login?error=exchange", status_code=303)

    user = token.get("user") or {}
    email = (user.get("email") or "").lower()
    meta = user.get("user_metadata") or {}
    name = meta.get("full_name") or meta.get("name") or (email.split("@")[0] if email else "")

    if not auth.is_allowed(email):
        resp = RedirectResponse("/login?error=denied", status_code=303)
        auth.clear_session(resp)
        return resp

    resp = RedirectResponse("/", status_code=303)
    auth.set_session(resp, email, name)
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    auth.clear_session(resp)
    return resp
