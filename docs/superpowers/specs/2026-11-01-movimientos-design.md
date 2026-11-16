# Diseño: sección Movimientos

Fecha: 2026-11-01 · Rama: `feature/movimientos` (parte de `feature/dashboard`, PR #4)

> `docs/alcance.md` está en la rama `docs/alcance-proyecto` (PR #2), todavía sin mergear. Sus reglas sobre movimientos son solo las que se citan en este documento: monto mayor que 0, categoría del mismo tipo que el movimiento y crear, editar y eliminar. No define monto máximo ni cuentas o categorías inactivas.

## Intención

`/movimientos` hoy es una página "en construcción". Esta sección cubre dos puntos de la Fase 1 de `docs/alcance.md`:

- **Historial:** lista de movimientos con filtros por fecha, categoría, cuenta y tipo.
- **Registro:** crear, editar y eliminar movimientos ("formulario/modal rápido para registrar").

Es el destino de "Ver todos" en la tarjeta *Recientes* del Resumen y del botón **Nuevo movimiento** de la barra lateral.

**Éxito:** registrar un gasto toma segundos desde cualquier sección, y en un vistazo se responde "¿en qué gasté este mes?" y "¿cuánto gasté en X desde la cuenta Y?".

## Objetivos

1. Ver todos los movimientos de un mes, agrupados por día, del más reciente al más antiguo.
2. Filtrar por tipo, cuenta, categoría y texto, con totales que reflejan el filtro.
3. Crear, editar y eliminar movimientos desde un formulario en un diálogo.
4. Dejar un contrato estable (esquemas, servicio y API JSON) para que el backend solo cambie las consultas, igual que en el Resumen.

## Fuera de alcance (no se construye)

- Transferencias entre cuentas y movimientos recurrentes (Fase 2).
- Exportar a CSV o PDF (Fase 3).
- Rangos de fechas libres: el mes es la unidad de navegación.
- Edición o eliminación de varios movimientos a la vez.
- Deshacer una eliminación.
- Editar desde la tarjeta *Recientes* del Resumen (sigue siendo de solo lectura).

## Anti-objetivos (sería un fracaso aunque funcione)

- Que la sección se vea distinta del login y del Resumen: otros radios, sombras, colores de acento nuevos o gastos en rojo.
- Que filtrar dependa de JavaScript o que los filtros se pierdan al recargar o al usar el botón de atrás.
- Que el Resumen y Movimientos muestren cifras distintas para el mismo mes.
- Que la plantilla haga cuentas de negocio: los totales salen del servicio y el formato de las plantillas.

## Restricciones

- **Mismo stack:** FastAPI + Jinja2 renderizado en el servidor, CSS propio con `tokens.css` y JS sin librerías ni paso de build.
- **Sistema de diseño:** `docs/design-system.md` es obligatorio (ver la sección "Diseño visual" abajo).
- **Dinero:** siempre `Decimal`, monto positivo y el tipo dice si suma o resta (mismas reglas que `app/schemas/dashboard.py`).
- **Reglas de negocio** (`docs/alcance.md`): monto mayor que 0; un gasto no usa una categoría de ingreso ni al revés.
- **Backend de Evan:** el login real y la base de datos no existen aún. Se usa `USUARIO_DEMO` y datos de prueba con un `TODO(backend)` en cada punto que cambia.
- **Navegador:** View Transitions entre secciones como hoy; sin animación en Firefox. Todo respeta `prefers-reduced-motion`.

## Pantalla

### Barra superior

- Título "Movimientos" (`topbar__title`).
- En `{% block acciones %}`: el selector de mes `_selector_mes.html` con `ruta = "movimientos"`. Los enlaces del selector **conservan los filtros activos** (solo cambian `anio` y `mes`).
- No se agrega otro botón "Nuevo": el de la barra lateral ya cumple esa función.

### Tarjeta de totales

Una `.card` con tres cifras en fila: **Ingresos**, **Gastos** y **Balance**.

- Etiqueta en `.label`, cifra en `.mid` con `.num`.
- Ingresos en `--color-income` con "+". Gastos en `--color-text` con "−".
- Balance: positivo o cero en `--color-income` con "+"; negativo en `--color-text` con "−". **Nunca en rojo** (el rojo es solo para presupuestos excedidos, errores y acciones destructivas).
- **Reflejan los filtros activos.** Con un filtro, debajo aparece en `.sub`: "Según los filtros".

### Barra de filtros

Una fila, encima de la lista, sobre el fondo `--color-canvas` (no dentro de una tarjeta):

1. **Buscar:** input en píldora con ícono de lupa, mismo estilo que `.float-field__input` pero sin etiqueta flotante (`placeholder="Buscar"`, con `aria-label`). Busca en la descripción y en el nombre de la categoría, sin distinguir mayúsculas ni tildes.
2. **Tipo:** control segmentado *Todos · Ingresos · Gastos* (componente nuevo, ver abajo).
3. **Cuenta:** select en píldora ("Todas las cuentas" + cada cuenta).
4. **Categoría:** select en píldora ("Todas las categorías" + categorías agrupadas en `<optgroup>` *Gastos* e *Ingresos*).
5. **Quitar filtros:** enlace (`--color-link`) que aparece solo con algún filtro activo; lleva al mismo mes sin filtros.

Funcionamiento:

- Es un `<form method="get" action="/movimientos">` con campos ocultos `anio` y `mes`. Los parámetros son `tipo` (`ingreso|gasto`), `cuenta` (id), `categoria` (id) y `q` (texto).
- **Sin JavaScript** funciona con un botón "Filtrar". **Con JavaScript** (`movimientos.js`) el botón se oculta y el formulario se envía solo al cambiar un select o el segmentado, y 300 ms después de dejar de escribir en la búsqueda.
- Un parámetro inválido (id que no existe, tipo desconocido) se ignora, como si no estuviera.

### Lista agrupada por día

Una `.card` que contiene todos los días del mes filtrado.

- **Encabezado de día:** fecha larga ("Viernes 31 de octubre") en `.label` a la izquierda y el **total neto del día** a la derecha en `.num`, con los mismos colores y signos que el balance.
- **Filas:** mismo markup que la tarjeta *Recientes* (`.rows`, `.rows__name`, `.icon-bubble` con `iconos.categoria`). Primera línea: descripción. Línea `.sub`: "Categoría · Cuenta" (la fecha ya está en el encabezado del día). Monto a la derecha: `dinero("+")` con `.income` o `dinero("-")`.
- **Descripción vacía:** se muestra el nombre de la categoría.
- **Orden:** días del más reciente al más antiguo; dentro del día, del más nuevo al más viejo según el id.
- **Cada fila es un `<button>`** (accesible con teclado) que abre el diálogo en modo edición. Hover: fondo `--color-canvas` con `--radius-small`.
- **Fila recién guardada:** se resalta con fondo `--color-income-bg` que se desvanece en `--duration-slow`, y la página se desplaza hasta ella.
- **Entrada:** días escalonados con `style="--i: n"`, como el Resumen.

### Estados vacíos

Dentro de la tarjeta de la lista, con el patrón de `.pending` (ícono, título `.card-title`, texto y botón):

- **Mes sin movimientos:** "No hay movimientos en octubre" + botón `btn--outline` "Registrar un movimiento", que abre el diálogo.
- **Filtros sin resultados:** "Ningún movimiento coincide con los filtros" + botón `btn--outline` "Quitar filtros".

## Diálogo "Nuevo movimiento" / "Editar movimiento"

### Dónde vive y cómo se abre

- El `<dialog>` vive en `base_app.html`, así que se abre desde **cualquier sección**.
- El botón de la barra lateral pasa a ser `<a href="/movimientos?nuevo=1">` mejorado con JS:
  - Con JS abre el diálogo en la página actual sin navegar.
  - Si se llega a `/movimientos?nuevo=1` (por ejemplo, abriendo el enlace en otra pestaña), la plantilla marca `data-abrir-dialogo` y el JS abre el diálogo al cargar.
- **Registrar, editar y eliminar requieren JavaScript**, igual que el login: escriben con `fetch` contra la API JSON. No hay rutas POST que devuelvan HTML. Lo que sí funciona sin JS es ver la lista, filtrar y cambiar de mes. Sin JS, el diálogo no se muestra y las filas no son clicables (el `<button>` de cada fila se agrega desde el JS, o se oculta con la clase `no-js`).
- Las filas de la lista lo abren en modo edición con los datos de esa fila (van en atributos `data-*` de la fila; no hace falta pedirlos al servidor).

### Aspecto (igual que la tarjeta del login)

- Superficie blanca, `--radius-card`, `--card-padding`, **sin sombra**. El fondo detrás es el `.scrim` que ya existe para el cajón del celular.
- Ancho 480 px centrado en escritorio. En el celular (≤ 760 px) ocupa la pantalla completa.
- Entra con `--duration-slow` y `--ease-emphasized`: desplazamiento de 8 px y fundido. Con movimiento reducido aparece sin animación.
- Título `.card-title`: "Nuevo movimiento" o "Editar movimiento". Botón de cerrar (×) arriba a la derecha. Esc y clic en el fondo también cierran.

### Campos (en este orden)

1. **Tipo:** control segmentado *Gasto · Ingreso*. Por defecto, Gasto.
2. **Monto:** `.float-field` con la etiqueta "Monto" y la cifra a `--text-title` en `.num`. Acepta solo dígitos y muestra separadores de miles mientras se escribe ("184.300"). Envía el número sin formato.
3. **Categoría:** select en píldora con **solo las categorías del tipo elegido**. Al cambiar el tipo, la lista se actualiza; si la categoría elegida ya no aplica, queda sin selección.
4. **Cuenta:** select en píldora.
5. **Fecha:** `.float-field` con `type="date"`. Por defecto, hoy. No acepta fechas futuras (`max` = hoy).
6. **Descripción:** `.float-field` opcional, máximo 80 caracteres.

Errores de cada campo en `.field__message--error`, y errores generales en `.alert--danger` arriba del formulario: mismos componentes y textos cortos que el login.

### Botones

- **Guardar:** `btn--primary btn--lg btn--block`, con los estados `is-loading` (spinner) e `is-success` (check) que ya existen en el login. Es el único azul de la pantalla mientras el diálogo está abierto.
- **Eliminar** (solo al editar): botón de texto en `--color-danger`, alineado a la izquierda bajo Guardar. Pide confirmación dentro del mismo diálogo, reemplazando su contenido: "¿Eliminar *Taxi* por −62.000? No se puede deshacer." con los botones "Eliminar" (fondo `--color-danger`) y "Cancelar" (`btn--outline`).

### Después de guardar o eliminar

1. Se cierra el diálogo.
2. Se recarga la sección actual. Si se guardó desde Movimientos y la fecha cae en otro mes, se navega a ese mes con los filtros vacíos.
3. En Movimientos, la fila guardada se resalta (`?guardado=<id>`).
4. Aparece un **aviso** (componente nuevo): "Movimiento guardado" o "Movimiento eliminado".

## Componentes nuevos (se documentan en `docs/design-system.md`)

| Componente | Cómo se ve | De dónde sale |
|---|---|---|
| Control segmentado | Píldora con fondo `--color-canvas`; la opción elegida es una píldora blanca con `--ring-strong`. Radios nativos ocultos y accesibles. | Botones e inputs en píldora; `--ring-strong` = "control seleccionado" en `tokens.css` |
| Select en píldora | Igual que `.float-field__input`: borde `--color-border-strong`, `--radius-pill`, foco `--focus-ring`, flecha propia en SVG | Formulario del login |
| Diálogo | Tarjeta blanca de 28 px sin sombra sobre `.scrim` | Tarjeta del login y cajón del celular |
| Aviso | Píldora negra (`--color-text`, como `btn--ink`) con texto blanco, abajo al centro, 4 s. `role="status"`. Sin sombra. | "Nuevo movimiento" en negro de la barra lateral |

No se agregan colores ni radios nuevos. No se usa vidrio: el diálogo va sobre un fondo opaco.

## Celular (≤ 760 px)

- **Totales:** las tres cifras pasan a una fila compacta con `--text-body`.
- **Filtros:** la búsqueda queda visible. Tipo, cuenta y categoría pasan a un botón "Filtros", que muestra cuántos hay activos ("Filtros · 2") y abre una hoja desde abajo con los mismos campos y un botón "Aplicar".
- **Diálogo:** pantalla completa.

## Contrato y arquitectura

Se sigue el patrón del Resumen: esquemas → servicio con datos de prueba → presentación → plantilla.

### Esquemas (`app/schemas/movimientos.py`)

```python
class CuentaRef(BaseModel): id: int; nombre: str
class CategoriaRef(BaseModel): id: int; nombre: str; tipo: Literal["ingreso", "gasto"]

class Movimiento(BaseModel):
    id: int
    fecha: date
    descripcion: str            # puede ser ""; la plantilla muestra la categoría
    categoria: CategoriaRef
    cuenta: CuentaRef
    tipo: Literal["ingreso", "gasto"]
    monto: Decimal              # > 0

class FiltrosMovimientos(BaseModel):
    tipo: Literal["ingreso", "gasto"] | None = None
    cuenta_id: int | None = None
    categoria_id: int | None = None
    q: str | None = None

class ListaMovimientos(BaseModel):
    anio: int; mes: int
    filtros: FiltrosMovimientos
    movimientos: list[Movimiento]       # ya filtrados, del más reciente al más antiguo
    ingresos: Decimal; gastos: Decimal  # de los movimientos filtrados

class MovimientoEntrada(BaseModel):    # cuerpo de crear y editar
    tipo: Literal["ingreso", "gasto"]
    monto: Decimal                      # > 0, máximo 2 decimales
    categoria_id: int
    cuenta_id: int
    fecha: date                         # no futura
    descripcion: str = ""               # máximo 80 caracteres, sin espacios a los lados
```

`MovimientoReciente` del Resumen se reemplaza por `Movimiento`. La plantilla del Resumen pasa a usar `m.categoria.nombre` y `m.cuenta.nombre`.

### Servicio (`app/services/movimientos.py`)

- `catalogo(usuario_id) -> tuple[list[CuentaRef], list[CategoriaRef]]`
- `listar(usuario_id, anio, mes, filtros) -> ListaMovimientos`
- `obtener(usuario_id, id) -> Movimiento | None`
- `crear(usuario_id, entrada) -> Movimiento`
- `actualizar(usuario_id, id, entrada) -> Movimiento` (error si no existe)
- `eliminar(usuario_id, id) -> None` (error si no existe)
- Valida las reglas de negocio y lanza `ErrorValidacion` con un dict `{campo: mensaje}`.

**Datos de prueba:** un almacén en memoria del proceso. Se reinicia al reiniciar el servidor, y cada función lleva su `TODO(backend)`.

- **Siembra perezosa por mes:** la primera vez que se pide un mes, se siembra con la plantilla de movimientos de prueba actual (los mismos días, descripciones y montos que hoy usa `services/dashboard.py`). Así, cualquier mes tiene datos, como hoy en el Resumen, y los tests que piden meses fijos (octubre o febrero de 2026) obtienen siempre las mismas cifras, sin importar la fecha en que corran.
- **Sin fechas futuras:** en el mes en curso solo se siembran los días que ya pasaron (día ≤ hoy). Los meses futuros no se pueden pedir: `_periodo` ya lo impide.
- Lo creado, editado o eliminado en un mes ya sembrado se conserva mientras el proceso siga vivo.
- Los tests reinician el almacén con una función `reiniciar()` (fixture de pytest), para que no dependan del orden en que corren.

El Resumen deja de tener su propia lista: `services/dashboard.py` calcula ingresos, gastos, categorías y recientes **a partir de `movimientos.listar()`**. Así, un movimiento nuevo aparece también en el Resumen y las cifras coinciden. Los saldos de las cuentas siguen siendo de prueba (cuentas es otra sección).

**Catálogo de prueba:**
- Cuentas: Cuenta de ahorros, Billetera digital y Efectivo.
- Categorías de gasto: Mercado, Transporte, Arriendo, Ocio y Otros gastos.
- Categorías de ingreso: Salario y Otros ingresos.

### Presentación (`app/web/presentacion.py`)

`vista_movimientos(lista)` agrupa por día, calcula el neto de cada día y el balance, y dice si hay filtros activos. Solo hace cuentas de presentación, como `vista_resumen`.

Filtro nuevo en `formato.py`: `fecha_larga` ("Viernes 31 de octubre").

### Rutas

| Ruta | Respuesta |
|---|---|
| `GET /movimientos?anio&mes&tipo&cuenta&categoria&q&nuevo&guardado` | HTML |
| `GET /api/v1/movimientos?anio&mes&tipo&cuenta_id&categoria_id&q` | 200 `ListaMovimientos` |
| `POST /api/v1/movimientos` | 201 `Movimiento` · 422 `{"errores": {campo: mensaje}}` |
| `PUT /api/v1/movimientos/{id}` | 200 `Movimiento` · 404 · 422 |
| `DELETE /api/v1/movimientos/{id}` | 204 · 404 |

La API va en un router aparte (`app/api/movimientos.py`), con JSON y el mismo formato de errores para que el JS lo muestre por campo. El diálogo usa `fetch` como `login.js` (JSON, `credentials: "same-origin"`).

### JavaScript

- `static/js/movimiento-dialogo.js` (en `base_app.html`): abre y cierra el diálogo, filtra las categorías por tipo, da formato al monto, valida, envía y muestra errores y el aviso.
- `static/js/movimientos.js` (solo en Movimientos): envío automático de filtros, hoja de filtros en el celular y resaltado de la fila guardada.

### Estilos

`static/css/movimientos.css`, solo para esta sección. Los componentes nuevos compartidos (segmentado, select, diálogo y aviso) van en `app.css` porque el diálogo se usa en todas las secciones.

## Pruebas

- **Servicio:** filtros por tipo, cuenta, categoría y texto (sin distinguir tildes ni mayúsculas); totales del filtro; orden; validaciones (monto ≤ 0, categoría de otro tipo, fecha futura, id inexistente); crear, editar y eliminar.
- **Coherencia:** después de crear un gasto, `obtener_resumen` refleja el mismo total que `listar`.
- **API:** códigos 201, 200, 204, 404 y 422 con el formato de errores.
- **Página:** se renderiza con datos, con el mes vacío y con filtros sin resultados; el selector de mes conserva los filtros; `nuevo=1` agrega `data-abrir-dialogo`; un parámetro inválido se ignora.
- Los tests existentes del Resumen siguen pasando.

## Coordinación con el backend

Al terminar se le manda a Evan el contrato (esquemas y endpoints), como se hizo con el login y el dashboard. Él reemplaza el almacén en memoria por consultas a la base de datos sin tocar las plantillas ni la API.

## Decisiones tomadas por el equipo de frontend (revisables)

1. Un solo campo **Descripción**, opcional, en lugar de "nota" (el alcance dice "nota opcional"; el Resumen ya muestra una descripción).
2. **Gasto** es el tipo por defecto y **hoy** la fecha por defecto.
3. El **mes** es la unidad de navegación; no hay paginación ni rangos libres.
4. No se aceptan fechas futuras (coherente con el selector de mes, que no avanza más allá del mes actual).
5. Eliminar pide confirmación y no se puede deshacer.
6. Moneda: pesos colombianos sin decimales en pantalla, como el Resumen (la decisión de moneda sigue pendiente en `docs/alcance.md`).
7. Registrar, editar y eliminar requieren JavaScript, como el login. Sin JS solo se puede ver y filtrar.
8. Los datos de prueba se siembran por mes, la primera vez que se pide cada uno, sin días futuros en el mes en curso. Así los tests con meses fijos no cambian con la fecha.

## Lo que queda a criterio de quien lo construya

- Nombres internos de clases CSS nuevas, siempre que usen solo variables de `tokens.css`.
- Íconos de las categorías nuevas (Otros gastos, Otros ingresos, Salario), en el estilo de línea de `_iconos.html`.
- Textos de error, siempre cortos y en el tono del login.
