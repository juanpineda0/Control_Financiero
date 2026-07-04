# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Que es

App personal de registro de gastos para dos usuarios (pareja), en espanol y con montos en COP como enteros (`bigint`, sin decimales). Stack: FastAPI + Jinja2 (server-rendered, sin frontend aparte), Supabase (Postgres + Google OAuth) y despliegue en Vercel plan Hobby. No hay tests ni linter configurados.

**La v2 se desarrolla por fases**: la hoja de ruta esta en [docs/ROADMAP.md](docs/ROADMAP.md) — una fase por sesion, en orden. Antes de implementar, leer ese documento (incluye el SQL, los archivos y la verificacion de cada fase) y marcar el checkbox de la fase al terminarla.

## Comandos (Windows / PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1          # activar el venv
pip install -r requirements.txt
uvicorn app.main:app --reload         # http://localhost:8000
```

Requiere `.env` (copiar de `.env.example`): `app/config.py` valida las variables al importar el modulo, asi que sin `.env` la app ni arranca. La puesta en marcha completa (Supabase, Google OAuth, Vercel) esta en el README.

## Arquitectura

- **Entrada de Vercel**: [api/index.py](api/index.py) solo re-exporta `app` desde `app/main.py`; `vercel.json` enruta todo ahi (`@vercel/python` con `includeFiles: app/**`). [app/main.py](app/main.py) es solo el ensamblador (crea el `FastAPI()`, monta `/static`, incluye los routers y expone `/health`); las rutas reales viven en `app/routers/` (un modulo por area: `auth.py`, `expenses.py`, y las que se van sumando por fase segun [docs/ROADMAP.md](docs/ROADMAP.md)).
- **Auth** ([app/auth.py](app/auth.py) = logica, [app/routers/auth.py](app/routers/auth.py) = rutas): OAuth de Google via el endpoint GoTrue de Supabase con PKCE implementado a mano (no se usa el SDK para el login). Flujo: `/auth/start` genera verifier/challenge y guarda el verifier en cookie firmada de 10 min → Google → `/auth/callback` intercambia code+verifier contra `{SUPABASE_URL}/auth/v1/token?grant_type=pkce`. La sesion es una cookie firmada (itsdangerous) de 30 dias que guarda solo `{email, name}`; **el token de Supabase no se guarda, a proposito**. El control de acceso es la lista blanca `ALLOWED_EMAILS` (fail-closed: lista vacia = nadie entra).
- **Datos** ([app/db.py](app/db.py)): el servidor usa la key SERVICE_ROLE (cliente singleton con `lru_cache`). Las tablas tienen RLS habilitado pero **sin policies, por diseno**: la service-role lo salta y el control de acceso real es el login + lista blanca; la base es compartida entre los dos usuarios. Si algun dia se accede con la anon key, habria que escribir policies.
- **Esquema**: `schema.sql` esta **gitignoreado** (existe solo en local); los cambios de esquema se corren a mano en Supabase → SQL Editor. Si cambias el esquema, actualiza tambien el archivo local.
- **Keepalive**: `.github/workflows/keepalive.yml` hace curl diario a `/health` (secreto `APP_URL` = URL de produccion de Vercel), y `/health` toca la BD a proposito para contar como actividad y evitar la pausa del free tier de Supabase. No "optimizar" quitando esa consulta. El proyecto de Vercel debe tener **Deployment Protection desactivado** (Settings → Deployment Protection) o ni el keepalive ni los usuarios reales pueden llegar a la app — quedan atajados por el login de Vercel antes de llegar al login de Google de la app.
- **Constantes** ([app/categories.py](app/categories.py)): `CATEGORIES` y `PAYMENT_METHODS`; el POST de gastos valida contra ambas y cae al primer valor valido (`"Otros"` / `"Efectivo"`) si no coincide.
- **Fecha y mes** ([app/dates.py](app/dates.py)): todo "hoy" se calcula en `America/Bogota` (`today_bogota()`), nunca `date.today()` a secas (Vercel corre en UTC). La vista de gastos usa `?mes=YYYY-MM`; `parse_month_param`/`shift_month`/`month_bounds` son las utilidades para leer y navegar meses.
- **Formato de plata**: filtro Jinja `cop` (registrado en [app/templating.py](app/templating.py), instancia de `Jinja2Templates` compartida por todos los routers) da `$1.234.567`; no usar `"{:,.0f}".format(...)` suelto en templates nuevos.

## Convenciones y cuidados

- **El repo sera publico en GitHub**: nunca hardcodear correos personales, nombres de proyecto de Supabase ni secretos (los correos van solo en `ALLOWED_EMAILS` del `.env` / variables de Vercel). Los commits usan el correo noreply de GitHub.
- El Excel `Control finaciero *.xlsx` en la raiz es data personal: no commitearlo ni leerlo salvo que el usuario lo pida.
- Todo en espanol **sin tildes ni enes** (ASCII puro), tanto comentarios/docstrings como textos de la UI; el README si usa tildes.
- La columna `is_shared` y el checkbox "compartido" existen como base para el reparto 66/33 por ingresos de una fase futura (junto con resumenes mensuales, dashboards y ahorros). No eliminarlos aunque hoy no se usen para calcular nada.
