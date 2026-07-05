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
- [ ] Sesión 3 — Presupuestos
- [ ] Sesión 4 — Estadísticas
- [ ] Sesión 5 — Importar histórico del Excel (flexible: requiere solo la 1 y la 2)
- [ ] Sesión 6 — Ingresos y settle-up
- [ ] Sesión 7 — Día a día: ¿me ahorro por llevar comida al trabajo?

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
- **Rutas**: mover a `app/routers/` (expenses, savings, budgets, stats, incomes, habits)
  con `APIRouter`; `app/main.py` queda como ensamblador (app, static, templates,
  `include_router`, `/health`). Cálculos en `app/services/` como funciones puras
  (se trae el mes completo de Supabase y se agrega en Python: con 2 usuarios el volumen
  es mínimo, no hacen falta funciones SQL ni RPC).
- **Navegación**: tabs móvil-first en `base.html`: Gastos | Ahorros | Presupuesto |
  Stats | Más (ingresos, cuentas, hábitos). La app se usa desde el celular.
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

## Sesión 4 — Estadísticas

- `/stats?mes=`: total del mes, donut por categoría (Chart.js CDN), barras de gasto por
  día, comparativa vs mes anterior (Δ por categoría), gasto por persona, compartido vs
  no compartido, **por método de pago** (cuánto se fue a la tarjeta de crédito), **por
  quincena** (1–15 / 16–fin), promedio diario, proyección de cierre de mes al ritmo
  actual, top 10 gastos.
- Vista año: barras por mes y promedio mensual por categoría.
- `app/services/stats.py`: funciones puras (lista de gastos → agregados).
- Verificación: comparar totales contra sumas hechas a mano (o contra el Excel si el
  histórico ya se importó).

## Sesión 5 — Importar el histórico del Excel

Puede adelantarse; solo requiere las sesiones 1 y 2. Ideal hacerla antes de usar mucho
Stats, para arrancar con ~7 meses de historia.

- `scripts/import_excel.py` — script **local** (no corre en Vercel), usa `openpyxl`
  (instalarlo suelto o en `requirements-dev.txt`; NO en el `requirements.txt` de
  producción). El Excel es un archivo local gitignoreado (`*.xlsx`).
- Hojas mensuales: header en la fila 5, columnas A–E = Fecha, Monto, Origen→`description`,
  Categoría→mapa, "¿Quién lo pagó?"→`user_name`. Ignorar columnas auxiliares y el
  "Resumen por día". Defaults: `is_shared=true`, `payment_method='Efectivo'`.
- Mapa de categorías Excel→app como dict editable al inicio del script:
  Mercado (comida)→Mercado; Mercado (Aseo)→Hogar; Transporte trabajo→Transporte;
  Recreación→Entretenimiento; Luz/Internet/Gas→Servicios; Imprevistos→Otros;
  Cuota casa→**confirmar antes de correr** (¿Arriendo? ¿categoría nueva?).
- Hoja "Ahorros" (aportes por columnas: monto, quién, fecha) → `savings_contributions`
  de las metas correspondientes (crearlas antes desde la UI).
- SQL: `alter table public.expenses add column source text null;` — el import marca
  `source='excel'` para poder re-importar borrando `where source='excel'` (idempotente).
- Modo `--dry-run` que imprime el resumen (filas por hoja, total por categoría) sin
  insertar nada.
- Verificación: dry-run → importar → comparar el total por mes contra la celda "Total"
  de cada hoja del Excel.

## Sesión 6 — Ingresos y settle-up

- SQL:
  - `incomes`: id uuid pk, occurred_on date, amount bigint, user_name text, kind text
    check in ('Sueldo','Extra') default 'Sueldo', description text null, created_at.
  - `settlements`: id uuid pk, month date, from_user text, to_user text, amount bigint,
    settled_at timestamptz.
- `/ingresos`: formulario (fecha, monto, tipo, descripción) + lista del mes + total por
  persona; editar/borrar.
- **Proporción del mes** = ingresos de cada uno / total del mes. Si el mes no tiene
  ingresos registrados, usar la proporción del último mes que sí tenga.
- `/cuentas?mes=`: gastos compartidos del mes × proporción = cuota justa de cada uno; se
  compara contra lo que realmente pagó cada uno → "X le debe $Y a Z". Botón "marcar
  saldado" (inserta en `settlements`); los meses saldados quedan marcados.
- Stat extra: % de ahorro del mes = (ingresos − gastos) / ingresos.
- Verificación: mes de prueba con ingresos de ambos y gastos compartidos desbalanceados →
  validar la deuda contra una cuenta a mano; saldar y verificar el estado.

## Sesión 7 — Día a día: ¿me ahorro por llevar comida al trabajo?

Contexto real: uno de los dos recibe el almuerzo en su trabajo; el otro va a la oficina
solo algunos días y suele comprar mecato/desayunos y a veces almuerzo. La pregunta a
responder: ¿llevar comida hecha ahorra de verdad, y cuánto? (para decidir si vale el
tiempo de cocinar). La medición usa **datos reales**, no solo estimados:

- SQL: `office_days`: id uuid pk, day date, user_name text, brought_food boolean,
  note text null, unique(day, user_name).
- Check-in de 5 segundos en `/` (colapsable): "¿Hoy oficina?" → sí + "¿Llevaste comida?".
- Cruce: gasto del usuario en categorías de comida (constante configurable: `Mecato`,
  `Comida fuera`) en cada día de oficina.
- `/habitos` (o sección en Stats): promedio gastado en días que llevó vs días que no →
  ahorro real por día × días que llevó = "este mes te ahorraste ~$X por llevar comida";
  racha actual de días llevando; tabla de días de oficina del mes con su gasto.
- Si hay pocos días "no llevé" para comparar, usar presets estimados como contrafactual
  (constantes editables, p. ej. desayuno ~$8.000, almuerzo ~$18.000, mecato ~$5.000),
  marcándolo como "estimado".
- Extra opcional: botón genérico de "gasto evitado" (antojo que no compraste, con monto
  estimado) que suma al ahorro del mes y opcionalmente "abona" simbólicamente a una meta
  (idea de apps tipo Skip / No Spend Streak / NoBuy).
- Verificación: simular una semana (3 días de oficina, 2 llevando comida) con gastos
  reales y validar el cálculo a mano.

## Backlog (después de las 7 sesiones)

- PWA: manifest + ícono para "agregar a pantalla de inicio".
- Recurrentes con recordatorio (cuota casa, internet, luz): vencimientos + aviso; email
  gratis vía Resend free tier disparado por el cron de GitHub Actions existente.
- Export CSV del mes/año.
- Categorías en BD editables desde la UI (lo anticipa el docstring de `categories.py`).
- Presupuesto con override por mes puntual; rollover estilo YNAB.
- Vista de avance de las cuotas de la casa (proyectado vs pagado).

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

1. Flujo diario desde el celular: registrar gasto con método de pago → check-in de
   oficina.
2. Flujo mensual: registrar ingresos → revisar presupuesto (semáforos) → stats del mes →
   cuentas y saldar → aportar a metas.
3. Totales de stats del histórico importado == celda "Total" de cada hoja del Excel.
4. `/health` sigue OK (keepalive verde en Actions) y el deploy de Vercel funciona tras
   cada fase.
