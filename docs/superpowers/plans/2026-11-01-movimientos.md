# Movimientos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir la sección `/movimientos` (historial con filtros + diálogo para crear, editar y eliminar) con contrato, servicio de prueba y API JSON listos para que el backend solo cambie las consultas.

**Architecture:** Mismo patrón que el Resumen: `schemas` (contrato Pydantic) → `services` (almacén en memoria con `TODO(backend)`) → `web/presentacion` (cuentas de presentación) → plantillas Jinja2. Las escrituras van por una API JSON (`app/api/movimientos.py`) que usa el diálogo con `fetch`. El Resumen pasa a calcular sus cifras desde el servicio de movimientos.

**Tech Stack:** Python 3, FastAPI, Pydantic v2, Jinja2, pytest + TestClient, CSS con `tokens.css`, JS sin librerías.

**Spec:** `docs/superpowers/specs/2026-11-01-movimientos-design.md`

## Global Constraints

- Dinero siempre `Decimal`, monto > 0; el `tipo` (`"ingreso"|"gasto"`) dice si suma o resta.
- Solo variables de `app/static/css/tokens.css`. Sin sombras, sin degradados, sin peso 700, sin radios nuevos, sin colores nuevos. Gastos en `--color-text` con "−"; ingresos en `--color-income` con "+"; rojo solo para eliminar y errores; azul solo en "Guardar".
- Reutilizar `.card`, `.card-title`, `.label`, `.mid`, `.sub`, `.num`, `.income`, `.rows`, `.icon-bubble`, `.float-field*`, `.field__message--error`, `.alert--danger`, `.btn--primary/--outline/--lg/--block`, `.is-loading/.is-success`, `.scrim`, `.month`, `.pending`.
- Todo movimiento animado respeta `prefers-reduced-motion: reduce`.
- Textos de interfaz en español, cortos, tono del login.
- **Commits:** el usuario hace commit solo cuando lo pide. Los pasos "Commit" se acumulan y se proponen al final; no se ejecutan durante la implementación.
- Comando de pruebas: `.venv/bin/python -m pytest -q`.

## Review Focus

1. Búsqueda con tildes y mayúsculas ("CAFE" encuentra "Café"); `q` con solo espacios = sin filtro. → Task 1
2. Parámetros de filtro inválidos en la URL (`cuenta=abc`, `tipo=x`, `categoria=999`) se ignoran y la página responde 200. → Task 4
3. Editar un movimiento cambiando su fecha a otro mes: desaparece del mes viejo y aparece en el nuevo; el Resumen de ambos meses cuadra. → Task 1 y Task 2
4. Montos raros en la API: `0`, negativos, más de 2 decimales, texto. Responden 422 con `errores.monto`, nunca 500. → Task 3
5. El mes actual sin días sembrados (hoy es día 1) muestra el estado vacío, no un error. → Task 4

---

### Task 1: Contrato y servicio de movimientos

**Files:**
- Create: `app/schemas/movimientos.py`
- Create: `app/services/movimientos.py`
- Test: `tests/test_movimientos_servicio.py`

**Interfaces:**
- Produces (schemas): `CuentaRef(id:int, nombre:str)`, `CategoriaRef(id:int, nombre:str, tipo)`, `Movimiento(id, fecha, descripcion, categoria:CategoriaRef, cuenta:CuentaRef, tipo, monto:Decimal)`, `FiltrosMovimientos(tipo=None, cuenta_id=None, categoria_id=None, q=None)`, `ListaMovimientos(anio, mes, filtros, movimientos, ingresos:Decimal, gastos:Decimal)`, `MovimientoEntrada(tipo, monto, categoria_id, cuenta_id, fecha, descripcion="")`, tal como están en el spec.
- Produces (service):
  - `catalogo(usuario_id:int) -> tuple[list[CuentaRef], list[CategoriaRef]]`
  - `listar(usuario_id:int, anio:int, mes:int, filtros:FiltrosMovimientos|None=None) -> ListaMovimientos`
  - `obtener(usuario_id:int, id:int) -> Movimiento|None`
  - `crear(usuario_id:int, entrada:MovimientoEntrada) -> Movimiento`
  - `actualizar(usuario_id:int, id:int, entrada:MovimientoEntrada) -> Movimiento`
  - `eliminar(usuario_id:int, id:int) -> None`
  - `class ErrorValidacion(Exception)` con atributo `errores: dict[str, str]`
  - `class NoEncontrado(Exception)`
  - `reiniciar() -> None` (vacía el almacén; para tests)
  - `hoy() -> date` (función del módulo; los tests la reemplazan con `monkeypatch`)

**Valores fijos:**
- Cuentas: 1 "Cuenta de ahorros", 2 "Billetera digital", 3 "Efectivo".
- Categorías: 1 "Salario" (ingreso), 2 "Otros ingresos" (ingreso), 3 "Mercado", 4 "Transporte", 5 "Arriendo", 6 "Ocio", 7 "Otros gastos" (gasto).
- Plantilla de siembra: la lista `_MOVIMIENTOS` actual de `app/services/dashboard.py` (día, descripción, categoría, cuenta, tipo, monto), que se mueve a este módulo. El día se recorta al último día del mes (`min(dia, ultimo)`) como hoy.
- Siembra perezosa por `(anio, mes)` la primera vez que `listar`, `crear` o `actualizar` toca ese mes. En el mes de `hoy()` solo se siembran días `<= hoy().day`.
- Mensajes de `ErrorValidacion`: `monto`: "Escribe un monto mayor que 0."; `categoria_id` inexistente: "Elige una categoría."; categoría de otro tipo: "Esa categoría es de ingresos." / "Esa categoría es de gastos."; `cuenta_id` inexistente: "Elige una cuenta."; `fecha` futura: "La fecha no puede ser futura."; `descripcion` > 80: "Máximo 80 caracteres.".
- Orden: fecha descendente y, dentro del día, id descendente.
- Búsqueda: `q.strip()` sin distinguir mayúsculas ni tildes (`unicodedata` NFKD sin combinantes + `casefold`) sobre descripción y nombre de la categoría.

- [ ] **Step 1: Write the failing tests** (`tests/test_movimientos_servicio.py`, con fixture `autouse` que llama `reiniciar()` y fija `hoy()` en `date(2026, 11, 15)`)
  - `test_octubre_tiene_los_datos_de_prueba`: `listar(1, 2026, 10)` → 8 movimientos, `ingresos == Decimal("3200000")`, `gastos == Decimal("1874300")`.
  - `test_orden_del_mas_reciente_al_mas_antiguo`: fechas descendentes.
  - `test_mes_actual_sin_dias_futuros`: `listar(1, 2026, 11)` → todas las fechas `<= date(2026, 11, 15)`; con 15 de noviembre hay 2 (días 10 y 15).
  - `test_filtra_por_tipo_cuenta_y_categoria`: `tipo="gasto"` → `ingresos == 0` y `gastos == 1874300`; `cuenta_id=3` → solo "Efectivo"; `categoria_id=6` → total 180000.
  - `test_busqueda_sin_tildes_ni_mayusculas`: crear con descripción "Café" y buscar `q="CAFE"` → lo encuentra; `q="   "` → mismo total que sin filtro.
  - `test_crear_valida_reglas`: monto 0, categoría 1 con tipo gasto, cuenta 99, fecha 2026-11-16 y descripción de 81 caracteres → `ErrorValidacion` con la clave correspondiente y el mensaje exacto.
  - `test_actualizar_a_otro_mes_lo_mueve`: actualizar el "Taxi" de octubre a fecha 2026-09-05 → ya no está en octubre y sí en septiembre.
  - `test_eliminar_y_no_encontrado`: eliminar quita el movimiento; `eliminar(1, 9999)` y `actualizar(1, 9999, …)` lanzan `NoEncontrado`.
- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_movimientos_servicio.py -q` → FAIL (módulo no existe).
- [ ] **Step 3: Implement** los esquemas y el servicio con las firmas de arriba. Cada función pública lleva `# TODO(backend): consulta real filtrada por usuario_id`.
- [ ] **Step 4: Run** el mismo comando → PASS.
- [ ] **Step 5: Commit (diferido)** `feat(movimientos): Contrato y servicio con datos de prueba`

### Task 2: El Resumen se alimenta de movimientos

**Files:**
- Modify: `app/schemas/dashboard.py` (quitar `MovimientoReciente`; `movimientos_recientes: list[Movimiento]`)
- Modify: `app/services/dashboard.py` (calcula desde `movimientos.listar`)
- Modify: `app/templates/app/resumen.html` (`m.categoria.nombre`, `m.cuenta.nombre`, descripción vacía → categoría)
- Test: `tests/test_dashboard.py` (fixture `reiniciar`), `tests/test_movimientos_servicio.py`

**Interfaces:**
- Consumes: `listar`, `Movimiento` (Task 1).
- Produces: `obtener_resumen(usuario_id, anio, mes) -> ResumenDashboard`, misma firma de antes.

- [ ] **Step 1: Write the failing test** `test_resumen_y_movimientos_coinciden`: después de `crear` un gasto de 50000 en octubre de 2026, `obtener_resumen(1, 2026, 10).gastos_mes == listar(1, 2026, 10).gastos == Decimal("1924300")` y el movimiento nuevo aparece en `movimientos_recientes`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** el cálculo de ingresos, gastos, categorías (por `categoria.nombre`) y recientes desde `listar(usuario_id, anio, mes)`. Los saldos de las cuentas se quedan como datos de prueba fijos.
- [ ] **Step 4: Run** `.venv/bin/python -m pytest -q` → PASS (incluye `test_resumen_muestra_las_cifras_del_contrato` y `test_recientes_del_mes…`).
- [ ] **Step 5: Commit (diferido)** `refactor(dashboard): El Resumen usa el servicio de movimientos`

### Task 3: API JSON de movimientos

**Files:**
- Create: `app/api/__init__.py`, `app/api/movimientos.py`
- Modify: `app/main.py` (incluir el router)
- Test: `tests/test_api_movimientos.py`

**Interfaces:**
- Consumes: servicio (Task 1), `USUARIO_DEMO` de `app/web/views.py` (mover a `app/web/sesion.py` para no importar vistas desde la API: `USUARIO_DEMO: dict`).
- Produces:
  - `GET /api/v1/movimientos?anio&mes&tipo&cuenta_id&categoria_id&q` → 200 `ListaMovimientos`
  - `POST /api/v1/movimientos` → 201 `Movimiento` | 422 `{"errores": {campo: mensaje}}`
  - `PUT /api/v1/movimientos/{id}` → 200 | 404 `{"detail": "No existe"}` | 422
  - `DELETE /api/v1/movimientos/{id}` → 204 | 404
- El cuerpo se recibe como `dict` (`Body`) y se valida con `MovimientoEntrada.model_validate`. Un `ValidationError` de Pydantic se convierte en `{"errores": {loc[0]: mensaje}}` con los mensajes de Task 1 (tipo inválido: "Elige gasto o ingreso."; fecha inválida: "Escribe una fecha válida."; número inválido o con más de 2 decimales: "Escribe un monto mayor que 0.").

- [ ] **Step 1: Write the failing tests**
  - `test_crear_devuelve_201_y_aparece_en_la_lista`
  - `test_errores_por_campo`: parametrizado con `monto` en `0`, `-5`, `"abc"` y `"10.555"` → 422 y `"monto" in r.json()["errores"]`; `tipo: "otro"` → `errores.tipo`.
  - `test_editar_y_eliminar`: PUT → 200 con los nuevos datos; DELETE → 204; segundo DELETE → 404.
  - `test_put_inexistente_404`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** el router (`APIRouter(prefix="/api/v1/movimientos")`).
- [ ] **Step 4: Run** `.venv/bin/python -m pytest -q` → PASS.
- [ ] **Step 5: Commit (diferido)** `feat(api): Endpoints de movimientos`

### Task 4: Página de Movimientos (lista, filtros, totales y estados vacíos)

**Files:**
- Modify: `app/web/formato.py` (filtro `fecha_larga`)
- Modify: `app/web/presentacion.py` (`vista_movimientos`)
- Modify: `app/web/views.py` (ruta `/movimientos`; los filtros se leen como `str | None` y se convierten a mano: inválido → `None`)
- Modify: `app/templates/app/_selector_mes.html` (variable opcional `consulta`: cadena ya codificada que se agrega a los enlaces)
- Create: `app/templates/app/movimientos.html`, `app/static/css/movimientos.css`
- Test: `tests/test_web_movimientos.py`, `tests/test_dashboard.py` (formato)

**Interfaces:**
- Consumes: `listar`, `catalogo`, `FiltrosMovimientos` (Task 1).
- Produces:
  - `fecha_larga(valor: date) -> str` → `"Viernes 31 de octubre"` (día de la semana con mayúscula inicial).
  - `vista_movimientos(lista: ListaMovimientos) -> dict` con claves `dias: list[dict(fecha, neto: Decimal, movimientos)]`, `balance: Decimal`, `hay_filtros: bool`.
  - Contexto de la plantilla: `lista`, `vista`, `periodo`, `catalogo` (cuentas, categorías), `consulta` (filtros codificados para el selector de mes), `abrir_dialogo: bool`, `guardado: int | None`.
- Marcado: el formulario de filtros es `<form class="filters" method="get" action="/movimientos" data-filtros>` con `anio`/`mes` ocultos y un `<button class="btn btn--outline" data-filtrar>Filtrar</button>`. Cada fila es `<li data-movimiento='{json}'>` (JSON con id, tipo, monto, categoria_id, cuenta_id, fecha y descripción), para que el JS de Task 5 la vuelva clicable. El contenedor lleva `data-abrir-dialogo` cuando `nuevo=1` y `data-guardado="<id>"` cuando corresponde.

- [ ] **Step 1: Write the failing tests**
  - `test_fecha_larga`: `fecha_larga(date(2026, 10, 31)) == "Viernes 31 de octubre"`.
  - `test_lista_agrupada_y_totales` (`/movimientos?anio=2026&mes=10`): contiene "Viernes 31 de octubre", "+$3.200.000", "−$1.874.300", "+$1.325.700" y "Cuenta de ahorros".
  - `test_filtros_en_la_url_y_quitar_filtros`: `?anio=2026&mes=10&tipo=gasto` → no contiene "+$3.200.000" en la lista, contiene "Según los filtros" y "Quitar filtros".
  - `test_selector_de_mes_conserva_filtros`: el enlace al mes anterior contiene `tipo=gasto`.
  - `test_parametros_invalidos_se_ignoran`: `?cuenta=abc&tipo=x&categoria=999` → 200 y sin "Según los filtros".
  - `test_estado_vacio_del_mes` (hoy fijado en el 1 de noviembre de 2026): `/movimientos?anio=2026&mes=11` → "No hay movimientos en noviembre".
  - `test_filtros_sin_resultados`: `?anio=2026&mes=10&q=zzz` → "Ningún movimiento coincide con los filtros".
  - `test_nuevo_abre_dialogo`: `?nuevo=1` → `data-abrir-dialogo` en el HTML.
  - En `test_archivos_de_la_app`, agregar `/static/css/movimientos.css`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** el filtro, la vista, la ruta, la plantilla (con las secciones del spec: totales, filtros, lista por día y estados vacíos) y `movimientos.css` (responsive ≤ 760 px: totales compactos; tipo, cuenta y categoría dentro de `<details class="filters__more">` con el resumen "Filtros · N", que en escritorio se muestra siempre abierto).
- [ ] **Step 4: Run** `.venv/bin/python -m pytest -q` → PASS.
- [ ] **Step 5: Commit (diferido)** `feat(movimientos): Lista con filtros y totales`

### Task 5: Diálogo de movimiento y componentes compartidos

**Files:**
- Modify: `app/templates/app/base_app.html` (el enlace de la barra pasa a `/movimientos?nuevo=1` con `data-nuevo-movimiento`; incluye `_dialogo_movimiento.html`, el contenedor del aviso y el script)
- Create: `app/templates/app/_dialogo_movimiento.html`
- Modify: `app/web/views.py` (`_contexto_app` agrega `catalogo` y `hoy`)
- Modify: `app/static/css/app.css` (control segmentado `.segmented`, `.select`, `.dialog`, `.toast`)
- Create: `app/static/js/movimiento-dialogo.js`, `app/static/js/movimientos.js`
- Modify: `docs/design-system.md` (sección "Componentes de formulario y diálogos")
- Test: `tests/test_web_movimientos.py`, `tests/test_web_app.py`

**Interfaces:**
- Consumes: la API (Task 3) y el marcado `data-*` (Task 4).
- Produces:
  - `<dialog class="dialog" id="dialogo-movimiento" aria-labelledby="dialogo-titulo">` con un `<form data-form-movimiento novalidate>` y los campos `tipo` (radios en `.segmented`), `monto` (`inputmode="numeric"`), `categoria_id` (`<select>` con `<option data-tipo>`), `cuenta_id`, `fecha` (`max` = hoy) y `descripcion` (`maxlength="80"`). Mensajes en `<p class="field__message field__message--error" id="<campo>-error" hidden>`.
  - `window.dialogoMovimiento.abrir(movimiento | null)` (lo usa `movimientos.js` al hacer clic en una fila).
  - Aviso: `<div class="toast" role="status" data-toast hidden>`. El texto pendiente se guarda en `sessionStorage["aviso"]` antes de recargar y se muestra al cargar la página siguiente.
  - `movimientos.js`: envía los filtros automáticamente (al cambiar selects y radios, y 300 ms después de escribir), oculta `[data-filtrar]`, vuelve clicables las filas `data-movimiento` (`role="button"`, `tabindex="0"`, Enter y Espacio), abre el diálogo si hay `data-abrir-dialogo` y resalta y desplaza hasta `data-guardado`.

- [ ] **Step 1: Write the failing tests**
  - `test_dialogo_en_todas_las_secciones` (parametrizado sobre `SECCIONES`): contiene `id="dialogo-movimiento"`, las 7 categorías con `data-tipo` y `max="<hoy ISO>"`.
  - `test_boton_nuevo_movimiento`: contiene `href="/movimientos?nuevo=1"` y `data-nuevo-movimiento`.
  - En `test_archivos_de_la_app`, agregar los dos JS nuevos.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** la plantilla, los estilos (ver la tabla "Componentes nuevos" del spec), el JS (formato de miles mientras se escribe, filtrar categorías por tipo, `fetch` con JSON a POST o PUT y DELETE, errores por campo, `.is-loading`/`.is-success` en Guardar, confirmación de eliminar dentro del diálogo, Esc y clic en el fondo para cerrar, recarga a `?anio&mes&guardado=<id>` del mes del movimiento cuando se está en Movimientos) y la documentación.
- [ ] **Step 4: Run** `.venv/bin/python -m pytest -q` → PASS.
- [ ] **Step 5: Verificación en el navegador** (servidor en el puerto 8000): crear un gasto desde el Resumen, verlo en Movimientos resaltado, editarlo, cambiarle el mes, eliminarlo, probar filtros, celular (≤ 760 px) y teclado (Tab, Enter, Esc).
- [ ] **Step 6: Commit (diferido)** `feat(movimientos): Diálogo para registrar, editar y eliminar`

### Task 6: Cierre

- [ ] Correr toda la suite y revisar el diff completo contra el spec.
- [ ] Redactar el mensaje para Evan con el contrato (esquemas y endpoints), como en el login y el dashboard.
- [ ] Proponer al usuario los commits diferidos y el PR hacia `develop` (depende del PR #4).
