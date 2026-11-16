# Auditoría de rendimiento: pendientes (3 de noviembre de 2026)

Dos auditorías hechas con subagentes, en solo lectura:

- **Login.** 7 ángulos. Sus arreglos de frontend ya se aplicaron en el commit `c743db9` (PR #12). Aquí solo queda lo pendiente.
- **Dashboard (`/resumen`).** 10 ángulos. **La sección A se aplicó el 4 de noviembre** (sin commit todavía), salvo `_dias` de A8, que se dejó porque la alternativa medida era más lenta. B, C y D siguen pendientes.

Medí con Chromium 155 headless por CDP. Las cifras "×4" son con la CPU ralentizada cuatro veces. El "móvil" es de 390 px con 150 ms de RTT y 1,6 Mbps. Headless pinta sin GPU, así que los tiempos absolutos de pintado salen inflados; sirven para comparar.

Las líneas citadas son las del 3 de noviembre. Antes de tocar algo, confírmalas con `grep`.

**Dueños:**

- **Juan:** el frontend (plantillas, CSS, JS), la orquestación de `app/web/` y la IA.
- **Evan:** el backend y la infraestructura (`app/main.py`, el almacén en memoria que se reemplazará por la base de datos). Lo de Evan solo se toca si Juan lo pide.

---

## A. Dashboard: frontend (Juan)

### A1. El `backdrop-filter` de la barra superior traba el scroll y la barra lateral. Impacto alto.

- **Dónde:** `app/static/css/app.css:286-290`. `.topbar` es sticky y lleva `saturate(1.8) blur(20px)` sobre un blanco al 80 %.
- **Scroll:** con el filtro va a 55-59 FPS, con un p95 de 33 ms y el peor frame en 66 ms. Sin él, 60 FPS y el peor frame en 16,8 ms.
- **Contraer o expandir la barra lateral:** 38-46 FPS con el filtro, 60 FPS sin él.
- **GPU:** `DirectRenderer::DrawRenderPass` durante el scroll tarda 227-370 ms con el blur y 88-115 ms sin él.
- **También en el diálogo:** este filtro y el de A2 suman 8-24 ms al pintado al abrir o cerrar el diálogo de movimiento.
- **Corrección:** fondo opaco (`var(--color-surface)`) con una línea inferior. Si se quiere mantener el vidrio, `blur(8px)` y activarlo solo cuando hay scroll.

### A2. Un `backdrop-filter` que no aporta nada en las cápsulas. Impacto alto y cambio de una línea.

- **Dónde:** `app/static/css/resumen.css:80-81`. `.capsule` lleva `blur(6px) saturate(1.6)` sobre el fondo liso `#f5f5f7` de `.stage`, así que no se ve ningún efecto.
- **Por qué cuesta:** las cápsulas animan `scaleY` durante 620 ms y el filtro se recalcula en cada frame.
- **Entrada:** 51-54 FPS con el peor frame en 50 ms. Sin ningún backdrop-filter, 58 FPS y 33 ms.
- **Corrección:** borrar esas dos líneas, igual que se hizo en el login (`login.css`, `.pv-savings__col`).

### A3. La transición de la barra lateral anima el layout. Impacto medio.

- **Dónde:** `app/static/css/app.css:58`, `transition: grid-template-columns`.
- **Costo:** recalcula el layout y repinta todo `.main` en cada frame. Son unos 13-14 layouts y unos 165 paints por clic; entre 40 y 56 de 140-170 frames pasan de 20 ms. A ×4, unos 77 ms de pintado por cambio.
- **Sin la transición:** 58 FPS y 20 ms de Paint, frente a 225-325 ms.
- **Corrección:** cambiar la clase dentro de `document.startViewTransition()`. La app ya usa View Transitions y `.sidebar` tiene `view-transition-name`. La otra opción es FLIP: una barra `position: fixed` que se mueve con `transform` y columnas que cambian de golpe.

### A4. La animación de entrada esconde el contenido y falsea el LCP. Impacto medio.

- **Dónde:**
  - `app/static/css/app.css:376-385`: `.view > *` arranca con `opacity: 0` y modo `both`, con un retraso de `--i` × 70 ms.
  - Barras: `resumen.css:87` (`grow-y`, 180 ms + 620 ms), `resumen.css:147` (`grow-x`, 260 ms + 520 ms) y `presupuestos.css:35-36` (`pista-in`, 200 ms + 700 ms).
- **Cuánto tarda:** la página no se ve completa hasta unos 900 ms después del primer pintado (son 11 animaciones). El contenido llega al 100 % de opacidad unos 300 ms después del FCP: en móvil, de 1124 a 1450 ms.
- **LCP:** Chrome descarta los elementos con opacidad 0, así que reporta el título `H1.topbar__title`. Con `prefers-reduced-motion`, el LCP real es `P.big` (144 ms en escritorio) o `P.stage__note` (1048 ms en móvil).
- **Cifras:** en escritorio, FCP = LCP = 168 ms y contenido visible a los 454 ms. En móvil con el mes 10, FCP de 996-1124 ms y contenido visible a los 1450 ms.
- **Corrección:** animar solo `transform`, sin `opacity` (o arrancar con opacidad 0,9). No escalonar el primer bloque. Que las barras crezcan sin retraso. Total de 500 ms o menos: retrasos de 80-120 ms y barras de unos 400 ms.

### A5. Cambiar de mes tarda 309 ms, y 185 son de la View Transition. Impacto medio.

- **Dónde:** `app.css:12-14` activa la transición entre documentos; la salida `vt-fuera` está en `app.css:33-35`.
- **Del clic al primer pintado:** 309 ms a ×1 y 431 ms a ×4. Con `prefers-reduced-motion` baja a 113 y 288 ms. El TTFB es de solo 16 ms.
- **Corrección:** en `app/static/js/app-shell.js`, en `pagereveal`, llamar a `e.viewTransition.skipTransition()` cuando la ruta anterior es la misma y solo cambian `anio` o `mes`. Así la animación se conserva para los cambios de sección.

### A6. Hay CSS que bloquea el pintado y que esta página no usa. Impacto medio.

- **Las 5 hojas que bloquean:** `base.html:12-13`, `base_app.html:15` y `resumen.html:6-7`. Suman 62 KB sin comprimir.
- **Uso real en `/resumen`:** `styles.css` 12 %, `presupuestos.css` 10 %, `app.css` 42 %, `resumen.css` 97 %.
- **`presupuestos.css` (10 KB) para una sola barra:** el Resumen solo necesita las líneas 1-98 (estado, pista y barra: 2,4 KB, 865 B con gzip). Hay que moverlas a `resumen.css` o a un `presupuesto-barra.css` y cargar `presupuestos.css` solo en `/presupuestos`. **Hay que ajustar también el prefetch de `login.html:11`.**
- **`styles.css`:** el 36 % es solo del login, unos 4,4 KB: `.global-nav` (`styles.css:101-192`), `.wordmark`, `.btn--shine`, `.float-field__action`, `.eye-slash` y `.check-fancy`. Va a `login.css`. Otro 32 % es solo del diálogo de movimiento.
- **`app.css`:** el 9 % no se usa (`.pending`, `.tono-*`, `.pago-*`, `.asistente__ejemplos`, de otras secciones) y el 26 % es solo del diálogo.
- **Más adelante:** unir `tokens.css`, `styles.css` y `app.css` en un solo archivo, sin lo del login.
- **Efecto en la carga:** el primer pintado en móvil es una tarea de unos 150 ms de estilo y layout (UpdateLayoutTree 55 ms + Layout 73 ms a ×4), más otro layout de 58 ms cuando llega la fuente. Ese costo baja al recortar el CSS.

### A7. El diálogo "Nuevo movimiento". Impacto medio.

Está en `app/static/js/movimiento-dialogo.js` y `app/templates/app/_dialogo_movimiento.html`, incluido en `base_app.html:88` y `:96` en todas las páginas.

- **Primera apertura (la peor interacción):** 40-56 ms a ×1 (máximo 72) y 80-88 ms a ×4 (máximo 144-168), con una tarea larga de 93-117 ms. Lo que cuesta:
  - `showModal()` (`:142`) vuelve inerte toda la página: 2,2 ms a ×1 y 9,6 a ×4.
  - `campos.monto.focus()` (`:143`) fuerza el estilo de los unos 304 elementos.
  - Hay que construir el árbol del diálogo, que estaba en `display: none`.
  - Aislado, todo esto suma 9,8 ms a ×1 y 53 ms a ×4. La primera vez se suma además el SVG en data-URI de la flecha del select (`app.css:620`): unos 17 ms a ×4.
- **Se inicializa entero aunque nunca se abra** (`:11-427`): unas 25 consultas al DOM, unos 20 listeners y `form.elements`.
- **Lee `sessionStorage` en cada carga** (`:404-413`, `sessionStorage.getItem(AVISO)`). Es una llamada IPC síncrona de 1,8 ms. Con ese bloque, EvaluateScript tarda 3,2-6,9 ms a ×1; sin él, 1,1-1,3 ms.
- **Correcciones:**
  - Inicialización perezosa: un `click` delegado en `[data-nuevo-movimiento]` y `const get = () => (api ??= init())` detrás de `window.dialogoMovimiento`. Se probó: EvaluateScript baja a 0,1-0,45 ms a ×1 y el diálogo abre bien.
  - Precalentar en `requestIdleCallback`: inicializar y forzar el estilo del `<dialog>` estando inactivo.
  - Pasar el aviso por la URL (`?aviso=guardado`) en `irDespues` y limpiarlo con `history.replaceState`. La otra opción es leerlo en `requestIdleCallback`.
  - **Ojo:** el aviso tras guardar se muestra desde este archivo (`:404-416`) y `asistente.js` depende de él. Antes de cargarlo de forma perezosa, mover el aviso a `app-shell.js`.
  - Flecha del select: un SVG en el HTML en lugar de una imagen CSS.
  - En `abrir()`, no hacer `form.reset()` y luego asignar los campos uno a uno.
- **Guardar:** del clic al primer pintado de la página siguiente pasan unos 1,13 s. Eso incluye 300 ms de latencia simulada y una **espera fija de 450 ms** (`:354`) para que se vea el check. Bajarla a unos 250 ms, o navegar en `animationend` como se hizo en el login.
- **HTML:** el diálogo ocupa 6.453 B, el 33 % del HTML de cada página (1.644 B con gzip) y unos 80 elementos. **No** recomiendo cargarlo con fetch con el volumen actual de datos: solo trae 7 categorías y 4 cuentas.

### A8. Servidor: orquestación en `app/web/` (Juan). Impacto bajo hoy y crece con los datos.

- **`url_for` es la mitad del render.** Se llama 13 veces por página (`base.html:8-13`, `base_app.html:15,95-97`, `resumen.html:6-7`) y cada llamada cuesta 18-25 µs, porque Starlette recorre las rutas y arma una URL absoluta `http://localhost:8000/static/...`. Con un `url_for` fijo, el render baja de 847 a 414 µs.
  - **Corrección:** un global `static(path)` en `app/web/views.py:26-29` que devuelva `"/static/" + path`. Afecta a todas las páginas, también al login.
  - Además, `auto_reload` de Jinja hace 8 `stat` por petición (unos 110 µs): ponerlo en `False` fuera de desarrollo.
- **El mes se lista dos veces por petición:** en `dashboard.py:19` y en `presupuestos.py:116` (llamado desde `del_mes:122`, vía `views.py:116-117`). Eso son 2 recorridos más 2 ordenaciones. Por eso un mes pasado con unos 2k movimientos cuesta el doble que el actual.
  - **Corrección:** listar una sola vez y pasar el resultado, por ejemplo `del_mes(..., gastos=...)`.
- **`cuentas.panel()` calcula `usos` y `pagos`, que el Resumen no usa** (`cuentas.py:202-203`, que pasa por `movimientos.py:121-127`, `usos_por_cuenta`). Con 10.500 movimientos son 7,8 ms de 13,4, y con 50k unos 37 ms.
  - **Corrección:** una función ligera `cuentas.saldos(usuario_id)` para el dashboard.
- **Llamadas repetidas en una misma petición:** `cuentas.listar` ×3 (`panel`, `_grupos_cuentas`, `catalogo`; `views.py:48-57`), `categorias.listar` ×2 y `hoy()` 6-7 veces. Leerlas una vez por petición.
- **`_dias` (`presupuestos.py:68`)** crea 31 modelos Pydantic por petición, unos 100 µs. Es menor.
- **Latencia actual:** `/resumen` p50 3,55 ms / p95 4,69 ms; con el mes 10, 4,0 / 5,4 ms. `/login`, 2,4 / 3,4 ms. El manejador completo, sin HTTP, tarda 1,76 ms.

### A9. Fuente en móvil. Impacto medio, pero hay que elegir qué se pierde.

- **Dónde:** `base.html:11` precarga `inter-latin.woff2` (47 KB), que compite con los 62 KB de CSS que bloquean a 1,6 Mbps. `app.css` termina a los 823 ms y la fuente a los 1017 ms.
- **Medición:** bloqueando la fuente, el FCP en móvil baja de 996-1064 ms a 784-860 ms (entre −140 y −280 ms).
- **Corrección:** un subconjunto más pequeño de Inter, o quitar la precarga y usar `size-adjust` en la fuente de respaldo para no generar CLS.

### A10. Detalles menores

- **Script en línea mal ubicado:** `base_app.html:14` queda después de `tokens.css` y `styles.css`, así que el parser espera al CSSOM; cuesta 2,5-5 ms. Moverlo antes de los `<link>` en `base.html`.
- **Listeners globales:** `desplegable.js` añade 3 listeners globales (`keydown`, `pointerdown`) por cada menú. Añadirlos al abrir y quitarlos al cerrar.
- **Espacio en blanco de Jinja:** `templates.env.trim_blocks = templates.env.lstrip_blocks = True` en `views.py:26`. Ahorra 2,6 KB sin comprimir y 286 B con gzip. Revisar a ojo los `{% if %}` en línea, como `stage__note`.
- **Análisis de la IA:** se podría pedir al pasar el puntero o al enfocar el botón (`analisis.js:77`) para esperar menos al hacer clic.

---

## B. IA: análisis y asistente

### B1. Gemini ocupa un hilo del threadpool y con muchas peticiones `/resumen` queda en cola. Impacto alto con usuarios reales.

- **Por qué:** las rutas son `def` (`app/api/ia.py:36`) y el cliente es síncrono (`app/services/ia.py:184`). No bloquea el bucle de eventos, pero el threadpool de AnyIO tiene 40 hilos que comparten todas las rutas `def`.
- **Medición:** con 45 análisis en curso (Gemini falso de 3 s), `/resumen` pasó de 0,01 s a **2,44 s**.
- **Por qué hoy no pasa:** solo existe el `USUARIO_DEMO` y el límite de 10 por minuto corta antes. De 15 peticiones simultáneas, 10 dieron 200 y 5 dieron 429.
- **Corrección:** `client.aio.models.generate_content` en rutas `async def`, o un `BoundedSemaphore` (unos 8) alrededor de `_generar`. **Nunca** convertir la ruta a `async def` dejando el cliente síncrono.

### B2. Tiempo máximo de 30 s, sin reintentos y sin cancelación. Impacto medio.

- **Servidor:** `TIEMPO_MAXIMO_MS=30_000` (`ia.py:51,155`), y httpx lo aplica por fase, no al total. Con `retry_options=None` se hace un solo intento. Si Gemini tarda 30 s, la persona ve el esqueleto durante 30 s y después "El asistente no respondió"; el hilo queda ocupado todo ese tiempo.
- **Cliente:** `analisis.js:120` no usa AbortController. Si la persona cambia de mes, el servidor sigue esperando y gasta la consulta.
- **Cupo:** `_registrar_consulta` (`ia.py:371`) descuenta del cupo aunque Gemini falle o `_limpiar_analisis` descarte la respuesta.
- **Corrección:** tiempo máximo de 10-15 s para el análisis, `AbortSignal.timeout` en el cliente y no descontar las consultas que fallan.

### B3. Dos peticiones simultáneas del mismo mes llaman dos veces a Gemini. Impacto medio.

- **Dónde:** la caché (`ia.py:367-375`) solo guarda al terminar. Se midió: 2 simultáneas hicieron 2 llamadas y la tercera salió de caché en 0,013 s.
- **Corrección:** un candado o future por clave para que la segunda espere a la primera.

### B4. Peticiones que se abandonan sin cancelar en el cliente. Impacto bajo.

- **Dónde:** en `asistente.js:190`, `disabled` evita el doble envío. Pero al cerrar el panel (`:170-174`) el botón se reactiva y la respuesta pendiente se ignora sin cancelarla. Si la persona reabre y envía, hay dos llamadas a la vez. Pasa lo mismo en `movimiento-dialogo.js:266`.
- **Corrección:** guardar un AbortController y llamar a `abort()` en `desplegable:cerrado` y antes de cada envío.

**Esto ya está bien:**

- La clave de caché es `(usuario, año, mes, texto de cifras)` y se invalida al crear un movimiento.
- La caché tiene un tope de 256 entradas y se vacía al llenarse. Podría ser LRU, pero no urge.
- El prompt no crece con el historial: son unos 478 caracteres.
- No se pide nada a la IA al cargar la página, y el doble clic está cubierto por `estado`.

---

## C. Backend e infraestructura (Evan; solo si Juan lo pide)

### C1. 🐛 Bug: errores 500 con peticiones concurrentes. Impacto alto (es de corrección, no de velocidad).

- **Qué pasa:** "dictionary changed size during iteration". Ocurre cuando un hilo recorre `_movimientos` (`movimientos.py:118,125,162`) mientras otro siembra un mes nuevo.
- **Frecuencia:** 1 error 500 en 6 rondas de 323 meses pedidos en paralelo. Con `sys.setswitchinterval(1e-6)` fallaron 161 de 323.
- **No se vieron** ids duplicados ni meses sembrados dos veces. Aun así, estas operaciones no son atómicas:
  - el patrón comprobar-y-luego-añadir de `_sembrar` (`movimientos.py:75-77`, `presupuestos.py:42-44`);
  - `_nuevo_id` (`movimientos.py:64-66`);
  - los contadores de `cuentas.py:289-293` y `:417-421`.
- **Corrección:** un `threading.Lock` alrededor de la siembra y los ids, o recorrer `list(_movimientos.values())`. Desaparece con la base de datos.
- **Script de reproducción:** `dash10/carrera.py` (ver "Scripts").

### C2. Los saldos recorren todo el historial en cada petición. Impacto alto con muchos datos.

- **Dónde:** `cuentas.py:158-164`. `_saldos` llama a `desde()` y aplica `_efecto` a cada movimiento desde `creada_en`.
- **Medición:** con cuentas viejas y 50k movimientos es el **61 %** del tiempo: 115 de 189 ms, con 500k llamadas a `_efecto`.
- **Con base de datos sigue importando.** El TODO de `movimientos.py:112` propone `desde()` como un SELECT de filas, y eso traería todo el historial a Python. Hace falta una consulta agregada: `SUM(CASE tipo …) … GROUP BY cuenta_id WHERE fecha >= creada_en`. Si crece mucho, conviene un saldo precalculado o un corte por mes.

### C3. Recorridos completos del almacén. Impacto medio y solo del almacén temporal.

- **Qué pasa:** cada `/resumen` recorre `_movimientos` entero 4 veces: `listar`, `desde`, `usos_por_cuenta` y `listar` desde presupuestos. No hay índice por mes.
- **Escala (`/resumen`, mediana de 15 GET):**

| N movimientos | Mes actual | Mes pasado (~2k) | Cuentas creadas hace 24 meses |
|---|---|---|---|
| 0 | 6,0 ms | 6,3 ms | 6,6 ms |
| 1k | 7,5 ms | 7,7 ms | 7,9 ms |
| 10k | 18,1 ms | 22,0 ms | 28,3 ms |
| 50k | 62,6 ms | 122,7 ms | 128,9 ms |

- Crece de forma lineal, no cuadrática.
- **Con base de datos:** el Resumen necesita `SUM … GROUP BY tipo, categoria` y los 4 recientes con `ORDER BY fecha DESC, id DESC LIMIT 4`, con un índice en `(usuario_id, fecha)`.
- **De paso:** `_sembrar` llama a `cuentas.ref_plantilla` por cada fila de la plantilla. Solo ocurre la primera vez.

### C4. Comportamiento bajo carga. Instancia propia, un worker, 2000 peticiones por fila.

| Ruta | Concurrencia | req/s | p50 | p95 | p99 |
|---|---|---|---|---|---|
| /resumen (almacén recién iniciado) | 1 / 10 / 50 / 100 | 252 / 339 / 318 / 297 | 3,5 / 27 / 125 / 217 ms | 6,7 / 49 / 249 / 477 ms | 9,7 / 69 / 571 / 2347 ms |
| /resumen (323 meses sembrados) | 1 / 10 / 50 / 100 | 148 / 135 / 170 / 169 | 5,8 / 69 / 273 / 395 ms | 11 / 121 / 389 / 940 ms | 15 / 173 / 720 / 3690 ms |
| /login | 1 / 10 / 50 / 100 | 410 / 419 / 468 / 628 | 2,3 / 21 / 87 / 103 ms | 3,9 / 41 / 161 / 181 ms | 5,3 / 59 / 341 / 1083 ms |

- La CPU llega a su techo con 10 conexiones.
- **Un solo worker:** `fastapi run` arranca uno solo, y no se puede subir mientras los datos vivan en memoria. Con base de datos, `--workers N` (la máquina tiene 8 núcleos) escala casi en proporción.
- **Memoria acotada:** 82,8 MB al arrancar, 93,9 MB tras sembrar 323 meses y 98,9 MB tras 20.000 peticiones más.
- **Rutas:** todas son `def`; nada bloquea el bucle de eventos.

### C5. Sin compresión. Afecta al login y al dashboard.

- **Dónde:** no hay `GZipMiddleware` en `app/main.py`.
- **Dashboard:** el texto pasa de 104 KB a 28 KB (−73 %). La primera visita baja de unos 152 KB a unos 80 KB, y el HTML de 19.123 B a 4.658 B (gzip) o 3.913 B (brotli).
- **Login:** el texto baja de 63 KB a 18 KB.
- **Corrección:** `app.add_middleware(GZipMiddleware, minimum_size=1000)`, o comprimir en el proxy.

### C6. `Cache-Control: no-cache` y sin versionado. Afecta al login y al dashboard.

- **Dónde:** `app/main.py:19-27`, clase `Estaticos`, con URLs sin hash.
- **Qué provoca:**
  - Cada navegación revalida todo. De Resumen a Movimientos: 10 respuestas 304 y 4 archivos nuevos. De Resumen a Presupuestos: 11 respuestas 304.
  - Con la red real, cada 304 cuesta 50-150 ms de RTT.
  - La visita repetida en móvil sigue en 708 ms de FCP.
- **Corrección:** un hash en la URL (desde un helper de Jinja) y `Cache-Control: public, max-age=31536000, immutable`. El HTML se queda sin caché.

### C7. Otros

- `HEAD /` y `HEAD /login` responden 405.
- `/` debería redirigir a `/login` cuando no hay sesión (TODO en `main.py:43`).
- El POST `/api/v1/auth/login` todavía no existe (da 404). Si la contraseña usa bcrypt o argon2, no hay que ejecutarlo dentro de una ruta `async`.

---

## D. Login: lo que quedó pendiente (los arreglos se aplicaron en `c743db9`)

- **D1. Haz del borde de la tarjeta:** sigue animando `--rim-angle` (`login.css`, alrededor de las líneas 96-107). Eso repinta en el hilo principal un `conic-gradient` con máscara `xor`. No se pudo pasar a `transform: rotate()` sin tocar el HTML: haría falta un elemento hijo con la máscara del aro y el degradado girando dentro. Por ahora va en su propia capa (`will-change: transform`) y la rasterización bajó de unos 740 a 390 ms.
- **D2. Estilo al mover el mouse:** quedan 116-132 tareas de más de 50 ms con CPU ×4, todas de estilo y no de JS. Las variables `--px/--py` y `--glare-*` se heredan y recalculan todo el subárbol, y hay `transition` sobre `transform` en elementos con backdrop-filter (`login.css`, líneas 340, 385 y 403). Sin `--px` el estilo baja a 4,9 s; sin el reflejo, a 3,1 s.
  - **Corrección:** registrar esas variables con `@property { inherits: false }` o escribir el `transform` directamente en las capas.
- **D3.** `.global-nav` (`styles.css`) mantiene su backdrop-filter.
- **D4. Opcionales:**
  - `contain: layout paint` en `.preview`.
  - Insertar la vista previa solo en escritorio (`<template>` + `matchMedia`): ahorra 8 KB y 126 nodos en móvil.
  - `Intl.NumberFormat("es-CO")` en `login-preview.js` podría costar a ×4, pero no se aisló.
  - `.pv-balance` con `min-width` y cifras tabulares.
- **D5.** C5 y C6 (compresión y caché) también afectan al login.

---

## E. Lo que ya está bien (no tocar)

- **Estabilidad visual:** CLS 0 en todos los casos, también con la barra lateral contraída, que el servidor pinta así desde el principio.
- **JS:** todo con `defer`. En reposo hay 0 ms de script, 0 timers y 0 rAF, y todas las animaciones terminan.
- **DOM:** unos 316 elementos, profundidad 13 y 25 SVG sin precisión de más. No hace falta un sprite de íconos.
- **Fuente:** inter-latin-ext no se descarga gracias a `unicode-range`, y el preload coincide con el `@font-face`.
- **Memoria:** acotada. Las cachés tienen tope.

## Scripts de medición

Están en el scratchpad de la sesión del 3 de noviembre: `/tmp/claude-1000/-home-juanpc-financial-management/6d038909-bb66-4d88-902d-0b74c1ce9c97/scratchpad/`. Son del dashboard (`dash1` a `dash10`), de la auditoría del login (`agente1` a `agente7`) y de sus arreglos (`arreglo-*`).

**Están en /tmp y pueden desaparecer.** Si hacen falta, hay que rehacerlos: Chromium está en `/usr/bin/chromium` y se maneja por CDP con Node, porque no hay Playwright en el venv.
