"""App FastAPI: ensambla los routers, sirve estaticos y expone /health."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .db import get_supabase
from .routers import auth, budgets, expenses, savings

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Finanzas")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(auth.router)
app.include_router(expenses.router)
app.include_router(savings.router)
app.include_router(budgets.router)


@app.get("/health")
def health():
    """Toca la BD para que cuente como actividad y evite la pausa de Supabase."""
    try:
        get_supabase().table("expenses").select("id").limit(1).execute()
        return {"status": "ok", "db": "up"}
    except Exception:
        return JSONResponse({"status": "error", "db": "down"}, status_code=500)
