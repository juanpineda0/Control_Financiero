# Hoja de ruta — Finanzas v2

Plan por fases para convertir la app v1 (login + formulario de gastos) en el reemplazo
completo del Excel con el que se manejaban las finanzas: ahorros con metas, presupuestos,
estadísticas, ingresos con reparto proporcional y hábitos del día a día.

**Cómo usar este documento**: cada sesión de desarrollo implementa UNA fase, en orden
(la 5 puede adelantarse). Antes de empezar una fase: leer `CLAUDE.md`, este documento y
la sección "Convenciones" de abajo. Al terminarla: marcar el checkbox, actualizar el
`schema.sql` local si hubo SQL, verificar en local y commitear.

## Estado

- [x] v1 — login Google + formulario de gastos + lista (hecho)
- [x] Sesión 1 — Base: navegación, método de pago, editar/borrar, vista mensual
- [x] Sesión 2 — Ahorros: metas y aportes
- [x] Sesión 3 — Presupuestos
- [x] Sesión 4 — Estadísticas (cerrada: los gráficos de ingresos se agregaron después de la Sesión 6)
- [x] Sesión 5 — Importar histórico del Excel (flexible: requiere solo la 1 y la 2)
- [x] Sesión 6 — Ingresos y settle-up
- [ ] Sesión 7 — Día a día: análisis con IA por fuera de la app (**sin código**, ver nota en la sección)

## Decisiones de diseño ya tomadas

1. **Categorías**: se mantienen las de `app/categories.py` (constante en código). El
   import del Excel mapea las categorías viejas a estas.
2. **Reparto de gastos compartidos**: settle-up mensual — cada gasto compartido se divide
   proporcional a los ingresos del mes de cada uno; la app calcula quién le debe cuánto a
   quién y se marca como saldado.
3. **Ingresos**: se registran por formulario (sueldo + entradas extra). La proporción del
   reparto sale de los ingresos registrados de ese mes.
4. **Método de pago** en gastos: `Efectivo` (default), `T. Debito`, `T. Credito`.
5. **Metas iniciales**: se crean desde la UI (no van seeded en código). Hay dos de ahorro
   y una tipo "deuda" (un consumo grande de tarjeta que se está abonando).
6. Los montos personales (sueldos, límites de presupuesto, metas) viven **solo en la base
   de datos**, nunca en el código ni en docs del repo.

## Arquitectura objetivo

- Mismo stack: FastAPI + Jinja2 SSR, formularios POST, sin build step ni framework JS.
  Chart.js por CDN únicamente en las páginas de estadísticas.
- **Rutas**: mover a `app/routers/` (expenses, savings, budgets, stats, incomes)
  con `APIRouter`; `app/main.py` queda como ensamblador (app, static, templates,
  `include_router`, `/health`). Cálculos en `app/services/` como funciones puras
  (se trae el mes completo de Supabase y se agrega en Python: con 2 usuarios el volumen
  es mínimo, no hacen falta funciones SQL ni RPC).
- **Navegación**: tabs móvil-first en `base.html`: Gastos | Ahorros | Presupuesto |
  Stats | Más (ingresos, cuentas). La app se usa desde el celular.
- **Zona horaria**: `date.today()` en Vercel es UTC → de noche en Colombia marca el día
  siguiente. Usar `ZoneInfo("America/Bogota")` y agregar `tzdata` a requirements.
- **Formato COP**: filtro Jinja `cop` → `$1.234.567` (puntos de miles).
- **Selector de mes** compartido: query param `?mes=YYYY-MM` + navegación ‹ › en Gastos,
  Presupuesto, Stats y Cuentas.
- **SQL**: cada fase trae su DDL. `schema.sql` está gitignoreado (solo local): el SQL se
  corre a mano en Supabase → SQL Editor y se actualiza el archivo local. Tablas nuevas
  con `enable row level security` sin policies (la service-role la salta), igual que
  `expenses`.

## Sesión 1 — Base

La fundación que las demás fases necesitan.

- SQL: `alter table public.expenses add column payment_method text not null default 'Efectivo';`
- `PAYMENT_METHODS = ["Efectivo", "T. Debito", "T. Credito"]` (constante, junto a las
  categorías); dropdown en el formulario con Efectivo preseleccionado, tag en la lista,
  validación con fallback a Efectivo (mismo patrón que la validación de categoría).
- **Editar y borrar gastos** (hoy imposible): GET de edición con form precargado +
  POST update + POST delete con confirmación.
- **Vista mensual completa** en `/` (no solo últimos 20): `?mes=`, total del mes arriba,
  navegación de mes.
- Split a `app/routers/`, tz Bogotá, filtro `cop`, tabs de navegación + estilos móviles.
- Actualizar README y CLAUDE.md si algo de lo anterior los desactualiza.
- Verificación: `uvicorn app.main:app --reload` → crear/editar/borrar un gasto con método
  de pago, navegar entre meses, y confirmar que de noche la fecha por defecto es la de
  Colombia.

## Sesión 2 — Ahorros: metas y aportes

- SQL:
  - `savings_goals`: id uuid pk, name text, kind text check in ('ahorro','deuda') default
    'ahorro', target_amount bigint, target_date date null, emoji text null, is_archived
    boolean default false, created_at timestamptz.
  - `savings_contributions`: id uuid pk, goal_id fk → savings_goals, amount bigint
    (negativo = retiro), occurred_on date, user_name text, note text null, created_at.
- `/ahorros`: tarjeta por meta con barra de progreso, `ahorrado / meta`, **cuota
  sugerida** = (meta − ahorrado) / meses hasta `target_date`, estado al día/atrasado,
  y desglose de aportes por persona.
- Detalle de meta: historial de aportes, form de aporte/retiro, editar meta, archivar
  (no borrar si tiene aportes).
- **Crear meta desde la UI**: nombre, tipo, monto objetivo, fecha opcional, emoji.
- Tipo `deuda`: labels "abonado / restante" y fecha estimada de pago al ritmo promedio.
- Verificación: crear las metas reales desde la UI, registrar un aporte y un retiro,
  revisar la cuota sugerida contra una cuenta a mano.

## Sesión 3 — Presupuestos

- SQL: `budgets`: id uuid pk, category text unique, monthly_limit bigint, updated_at.
- `/presupuesto`: fila por categoría con límite editable, gastado del mes, barra con
  semáforo (verde <80%, amarillo 80–100%, rojo >100%), disponible restante, totales del
  mes (presupuestado vs gastado vs disponible) y "ritmo" (cuánto por día queda para el
  resto del mes).
- Los límites aplican a todos los meses por igual (override por mes puntual → backlog).
- En `/` (Gastos): aviso discreto si alguna categoría pasa del 80%.
- Verificación: definir 2–3 límites, registrar gastos que crucen los umbrales, ver el
  semáforo cambiar.

## Sesión 4 — Estadísticas (hecha; se cerró después de la Sesión 6)

**Implementado** (`/stats?mes=`): hero con el total del mes + Δ vs mes anterior,
KPIs (promedio diario, proyección de cierre al ritmo actual), gasto por día (Chart.js),
gasto por categoría, comparativa vs mes anterior por categoría (Chart.js, barra
divergente rojo/verde), gasto por persona, compartido vs no compartido, **por método de
pago** (cuánto fue a tarjeta de crédito), **por quincena** (1–15 / 16–fin), top 10
gastos (tabla). Vista año (`/stats/anio?anio=`): barras por mes (Chart.js) + tabla de
promedio mensual por categoría, con selector de años reales.

**Decisión de diseño (distinta del plan original): sin donut.** Se sigue la guia de la
skill `dataviz` del repo: un donut/pie no es buena forma para >6 categorías ni para
comparar valores parecidos. "Gasto por categoría" quedó como una lista de barras
horizontales ordenadas (magnitud, un solo hue secuencial), igual de "bello" pero mas
legible con las 13 categorías de la app. La paleta categórica (`--series-1..8` en
`styles.css`, luz/oscuro) es la paleta de referencia validada CVD de esa skill.

`app/services/stats.py`: funciones puras (lista de gastos → agregados). Verificación
hecha: totales de varios meses comparados contra la app real, coinciden con lo
importado del Excel en la Sesión 5.

**Cierre (jul 2026), con la Sesión 6 ya hecha** — se agregaron las secciones que
dependían de `incomes`, todas como barras HTML (sin más Chart.js):

- **Ingresos vs gastos** del mes (dos barras de magnitud) + **% de ahorro**
  ((ingresos − gastos) / ingresos) con el balance en plata.
- **Gasto vs ingreso por persona**: barra tipo "meter" de lo gastado como parte del
  ingreso de cada quien (rojo si gasta más de lo que gana).
- **Reparto de lo compartido**: cuota justa (según proporción de ingresos, misma
  lógica y mismo fallback de mes que `/cuentas` — se reutiliza
  `ingresos_para_proporcion` y `app/services/settlement.py`) vs lo que realmente
  pagó cada quien, con el delta "puso $X de más/de menos" y link al settle-up.

Los cálculos nuevos son funciones puras en `app/services/stats.py`
(`gasto_vs_ingreso_por_persona`, `cuota_vs_pagado`). Verificación hecha: cuentas a
mano de proporciones/cuotas/deltas + render real de junio 2026 (ahorro 50,4%, las
cuotas suman exacto el total compartido); meses sin ingresos o sin datos muestran
mensajes vacíos con link a `/ingresos` en vez de romperse.

## Sesión 5 — Importar el histórico del Excel (hecha)

`scripts/import_excel.py` — script **local** (no corre en Vercel), usa `openpyxl`
(en `requirements-dev.txt`, NO en el `requirements.txt` de producción). El Excel es un
archivo local gitignoreado (`*.xlsx`); **`scripts/` tambien esta gitignoreado completo**
porque el script mapea nombres reales (`QUIEN_MAP`) y el repo es publico. Si hace falta
recrearlo, la logica completa (columnas, mapa de categorias, dedup) queda documentada aqui
abajo.

Decisión final (distinta del plan original): **sin columna `source`** — Juan prefirió que
los gastos importados queden indistinguibles de uno hecho a mano, sin marca de origen. La
idempotencia para poder correr el script mas de una vez sin duplicar se resuelve comparando
contra lo que ya hay en la BD (fecha+monto+categoría+quién para gastos; +goal_id para
aportes) y omitiendo lo que ya exista, en vez de borrar por `source='excel'`.

- Hojas mensuales (Sep 2025 a jun2026): header en la fila 5, columnas A–E = Fecha, Monto,
  Origen→`description`, Categoría→mapa, "¿Quién lo pagó?"→`user_name`. Mapa de categorías
  confirmado: Mercado (comida)→Mercado; Mercado (Aseo)→Hogar; Transporte trabajo→Transporte;
  Recreación→Entretenimiento; Luz→Servicios; Internet→Servicios; Imprevistos→Otros;
  Cuota casa→**Cuota Casa** (la app ya tenia esa categoria exacta desde la Sesion 1).
- Hoja "Ahorros": el script sabe leerla (`--sin-ahorros` para omitirla), pero en la
  practica Juan ya habia cargado esos aportes a mano, asi que el import real se corrio con
  `--sin-ahorros`.
- Modo `--dry-run` que imprime el resumen (filas por hoja, total por categoría) sin
  insertar nada.
- Verificación hecha: dry-run → importar (277 gastos) → comparar el total por mes contra
  la app real (`/?mes=YYYY-MM`) vs la celda "Total" de cada hoja del Excel. Cuadraron los
  7 meses (el de jun2026 con una diferencia esperada: el Excel llega solo hasta el 29, el
  30 de junio ya se habia registrado a mano en la app real).

## Sesión 6 — Ingresos y settle-up

**Nota:** al terminar esta sesión se volvió a la Sesión 4 (Estadísticas) y se
agregaron los gráficos de ingresos y de gasto compartido/propio que quedaban ahí
(ya hecho, ver la Sesión 4).

- SQL:
  - `incomes`: id uuid pk, occurred_on date, amount bigint, user_name text, kind text
    check in ('Sueldo','Extra') default 'Sueldo', description text null, created_at.
  - `transfers`: id uuid pk, occurred_on date, amount bigint, from_user text, to_user
    text, note text null, created_at. Son los pases de plata entre los dos durante el
    mes (ej. los viernes de pago); **no cuentan como ingresos** (no entran en la
    proporción del reparto: sería contar la plata dos veces).
  - `settlements`: id uuid pk, month date, from_user text, to_user text, amount bigint,
    settled_at timestamptz.
- `/ingresos`: formulario (fecha, monto, tipo, descripción, de quién) + lista del mes +
  total por persona; editar/borrar.
- **Proporción del mes** = ingresos de cada uno / total del mes. Si el mes no tiene
  ingresos registrados, usar la proporción del último mes que sí tenga.
- `/cuentas?mes=`: gastos compartidos del mes × proporción = cuota justa de cada uno; se
  compara contra lo que realmente pagó cada uno **y lo que ya se transfirieron entre
  ellos** → "X le debe $Y a Z". En la misma página: formulario para registrar
  transferencias del mes y su lista (borrar). Botón "marcar saldado" (inserta en
  `settlements` la deuda restante); los meses saldados quedan marcados. **Liquidación en
  cero**: al saldar se asume que se pagó la diferencia y cada mes arranca de cero (el
  sobrante/faltante no se arrastra).
- Stat extra: % de ahorro del mes = (ingresos − gastos) / ingresos.
- Verificación: mes de prueba con ingresos de ambos, gastos compartidos desbalanceados y
  transferencias → validar la deuda contra una cuenta a mano; saldar y verificar el
  estado.

## Sesión 7 — Día a día: ¿me ahorro por llevar comida al trabajo?

**Decisión (jul 2026): esta sesión NO se implementa en la app.** La pregunta se va a
responder con un análisis hecho con IA por fuera del código (conversación/análisis sobre
los datos ya registrados), no con tablas ni pantallas nuevas. En la app no se agrega SQL,
rutas ni UI por esta sesión; el checkbox se marca cuando ese análisis externo esté hecho.

Contexto real (sigue vigente como insumo del análisis): uno de los dos recibe el almuerzo
en su trabajo; el otro va a la oficina solo algunos días y suele comprar mecato/desayunos
y a veces almuerzo. La pregunta a responder: ¿llevar comida hecha ahorra de verdad, y
cuánto? (para decidir si vale el tiempo de cocinar).

El plan original de implementación (tabla `office_days`, check-in en `/`, `/habitos`,
presets de contrafactual, botón de "gasto evitado") queda descartado de esta fase; si
algún día se quiere medir dentro de la app, esas ideas pasan al backlog de abajo.

## Backlog (después de las 7 sesiones)

- PWA: manifest + ícono para "agregar a pantalla de inicio".
- Recurrentes con recordatorio (cuota casa, internet, luz): vencimientos + aviso; email
  gratis vía Resend free tier disparado por el cron de GitHub Actions existente.
- Export CSV del mes/año.
- Categorías en BD editables desde la UI (lo anticipa el docstring de `categories.py`).
- Presupuesto con override por mes puntual; rollover estilo YNAB.
- Vista de avance de las cuotas de la casa (proyectado vs pagado).
- Medición de hábitos dentro de la app (lo que era la Sesión 7 original): tabla
  `office_days`, check-in "¿Hoy oficina? ¿Llevaste comida?" en `/`, cruce con gasto en
  categorías de comida, `/habitos` con ahorro real por llevar comida, presets estimados
  como contrafactual y botón de "gasto evitado". Solo si el análisis externo con IA se
  queda corto.

## Convenciones (aplican a TODAS las sesiones)

- **Repo público**: cero correos, sueldos o montos personales en código o docs; los
  montos viven en la BD. Commits con el correo noreply de GitHub.
- Español **ASCII** (sin tildes ni eñes) en código, comentarios y UI; README/docs sí
  pueden llevar tildes.
- COP en enteros (`bigint`); mostrar siempre con el filtro `cop`.
- `schema.sql` es local/gitignoreado: correr el SQL a mano en Supabase SQL Editor y
  actualizar el archivo local en cada fase.
- Tablas nuevas: `enable row level security` sin policies (patrón existente).
- No tocar `/health` (el keepalive toca la BD a propósito) ni el flujo de auth
  (PKCE + cookie firmada, sin guardar el token de Supabase).
- Móvil primero; SSR simple, sin build step; solo Chart.js por CDN en stats.
- Verificar cada fase con `uvicorn` local contra la BD real antes de commitear;
  deploy = push a `master` (Vercel auto-deploy).

## Verificación end-to-end (al completar todo)

1. Flujo diario desde el celular: registrar gasto con método de pago.
2. Flujo mensual: registrar ingresos → revisar presupuesto (semáforos) → stats del mes →
   cuentas y saldar → aportar a metas.
3. Totales de stats del histórico importado == celda "Total" de cada hoja del Excel.
4. `/health` sigue OK (keepalive verde en Actions) y el deploy de Vercel funciona tras
   cada fase.
