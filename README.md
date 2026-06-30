# Finanzas

App para registrar gastos del día a día (efectivo y tarjeta), de uso personal para dos
personas. Backend en **FastAPI + Jinja2**, base de datos y login en **Supabase** (Google
OAuth), despliegue gratis en **Vercel**.

## Stack
- **FastAPI + Jinja2**: una sola app que sirve el HTML y guarda en la base de datos.
- **Supabase**: Postgres + autenticación con Google.
- **Vercel** (plan Hobby, gratis): hospedaje, siempre disponible.

## Estructura
```
api/index.py        Entrada para Vercel (expone la app FastAPI)
app/main.py         Rutas: login, callback, logout, "/", POST /expenses, /health
app/auth.py         OAuth Google (PKCE) + sesión por cookie firmada (30 días) + lista blanca
app/db.py           Cliente de Supabase (service-role)
app/config.py       Variables de entorno
app/categories.py   Lista de categorías del desplegable
app/templates/      base.html, login.html, index.html
app/static/         styles.css
schema.sql          Tabla `expenses` (correr en Supabase)
vercel.json         Config de despliegue
.github/workflows/keepalive.yml   Cron diario que evita la pausa de Supabase
```

---

## Puesta en marcha (local)

### 1. Entorno de Python
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Crear el proyecto en Supabase
1. Entra a https://supabase.com → **New project** (elige región cercana, ej. *East US*).
2. Cuando esté listo, ve a **SQL Editor** → pega el contenido de [`schema.sql`](schema.sql)
   → **Run**. Eso crea la tabla `expenses`.
3. Ve a **Project Settings → API** y copia:
   - **Project URL** → `SUPABASE_URL`
   - **anon public** → `SUPABASE_ANON_KEY`
   - **service_role** (secreta) → `SUPABASE_SERVICE_ROLE_KEY`

### 3. Configurar Google OAuth
**a) En Google Cloud Console** (https://console.cloud.google.com):
1. Crea/selecciona un proyecto.
2. **APIs & Services → OAuth consent screen**: tipo *External*, app *en producción* o agrega
   tus dos correos como *test users*.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID** → tipo
   *Web application*.
4. En **Authorized redirect URIs** agrega la URL de callback de Supabase:
   `https://TU-PROYECTO.supabase.co/auth/v1/callback`
5. Copia el **Client ID** y **Client secret**.

**b) En Supabase** → **Authentication → Providers → Google**: pega el Client ID y Client
secret, y **habilítalo**.

**c) En Supabase** → **Authentication → URL Configuration → Redirect URLs**, agrega:
- `http://localhost:8000/auth/callback`
- (más adelante) `https://TU-APP.vercel.app/auth/callback`

### 4. Variables de entorno
Copia `.env.example` a `.env` y rellena los valores. Genera el secreto de sesión con:
```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
Pon ambos correos en `ALLOWED_EMAILS` (solo esos podrán entrar).

### 5. Correr
```powershell
uvicorn app.main:app --reload
```
Abre http://localhost:8000 → **Entrar con Google** → registra un gasto. Verifícalo también
en Supabase → **Table Editor → expenses**.

---

## Despliegue en Vercel
1. Sube el proyecto a un repo de GitHub.
2. En https://vercel.com → **Add New → Project** → importa el repo.
3. En **Settings → Environment Variables** agrega las mismas variables del `.env`, pero
   `BASE_URL` = la URL de Vercel (ej. `https://tu-app.vercel.app`).
4. Agrega `https://tu-app.vercel.app/auth/callback` a los *Redirect URLs* de Supabase.
5. **Deploy**.

### Evitar la pausa de Supabase (keep-alive)
Supabase (free) pausa el proyecto tras 7 días sin actividad (los datos **no se pierden**;
se reactivan con 1 clic). Para que ni se pause, el workflow `keepalive.yml` hace `curl`
a `/health` una vez al día. Solo configura el secreto **APP_URL** en GitHub
(*Settings → Secrets and variables → Actions*) con la URL de tu app.

---

## Notas
- **Moneda:** se asume COP (una sola moneda).
- **Sesión:** cookie firmada de 30 días; tras ese tiempo se vuelve a iniciar sesión.
- **Pendiente (siguientes fases):** resúmenes por mes, reparto 66/33 por ingresos,
  dashboards y ahorros.
