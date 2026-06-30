"""App FastAPI: login con Google, formulario de gastos y lista de gastos recientes."""
from datetime import date
from pathlib import Path

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import auth
from .categories import CATEGORIES
from .db import get_supabase

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Finanzas")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# ------------------------------------------------------------------ Login
@app.get("/login", response_class=HTMLResponse)
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


@app.get("/auth/start")
def auth_start():
    """Genera PKCE y redirige a Google (via Supabase)."""
    verifier, challenge = auth.generate_pkce()
    resp = RedirectResponse(auth.build_authorize_url(challenge), status_code=303)
    auth.set_pkce_cookie(resp, verifier)
    return resp


@app.get("/auth/callback")
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


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    auth.clear_session(resp)
    return resp


# ------------------------------------------------------------------ App
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    recientes = (
        get_supabase()
        .table("expenses")
        .select("*")
        .order("occurred_on", desc=True)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
        .data
    )
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "user": user,
            "categories": CATEGORIES,
            "today": date.today().isoformat(),
            "expenses": recientes,
        },
    )


@app.post("/expenses")
def create_expense(
    request: Request,
    occurred_on: str = Form(...),
    amount: int = Form(..., gt=0),
    category: str = Form(...),
    description: str = Form(""),
    is_shared: bool = Form(False),
):
    user = auth.get_session(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    if category not in CATEGORIES:
        category = "Otros"

    get_supabase().table("expenses").insert(
        {
            "occurred_on": occurred_on,
            "amount": amount,
            "description": description.strip() or None,
            "category": category,
            "user_name": user["name"],
            "is_shared": is_shared,
        }
    ).execute()
    return RedirectResponse("/", status_code=303)


# ------------------------------------------------------------------ Salud
@app.get("/health")
def health():
    """Toca la BD para que cuente como actividad y evite la pausa de Supabase."""
    try:
        get_supabase().table("expenses").select("id").limit(1).execute()
        return {"status": "ok", "db": "up"}
    except Exception:
        return JSONResponse({"status": "error", "db": "down"}, status_code=500)
