# Sistema de diseño

Los tokens viven en `app/static/css/tokens.css`. Este documento explica de dónde salen y cómo usarlos.

## Referencia

`docs/design-referencia.md` es una ficha de [Refero](https://styles.refero.design/style/a4f123f2-cd4b-4d26-998f-a3d3ee158024) que describe el estilo de la página del iPhone Duo en apple.com. Es una **inspiración**, no una marca que copiamos: la app no usa el nombre, el logo, la fuente SF Pro ni imágenes de Apple.

**Qué conservamos de la referencia**

- Fondo gris `#f5f5f7` con tarjetas blancas de 28px de radio y **sin sombras**: la profundidad sale del contraste entre blanco y gris.
- Texto casi negro `#1d1d1f` y un único azul de acción. La interfaz es monocromática y el color es escaso.
- Botones e inputs en forma de píldora.
- Títulos en peso 600, nunca 700, y tracking negativo en el texto.
- Barra de navegación de 44px, blanca translúcida con desenfoque.

**Qué adaptamos al dashboard**

| Referencia (página de producto) | En la app | Por qué |
|---|---|---|
| Titular de 80px y secciones a pantalla completa | Máximo 40px (saldo total); 48px solo en login | Un dashboard muestra datos, no cuenta una historia |
| 90px entre secciones | 40px entre grupos de tarjetas | Más información visible sin hacer scroll |
| Sin colores de estado | Verde, naranja y rojo con fondo propio | Ingresos, alertas y excesos de presupuesto |
| Fotografía de producto como protagonista | Las cifras y gráficas son las protagonistas | No hay producto físico que mostrar |
| SF Pro | Inter en todos los dispositivos | SF Pro no tiene licencia para uso web; Inter es libre, muy parecida y se ve igual en cualquier equipo |

## Logo

La app se llama **Ziro** (se lee como "zero": el saldo cuadrado). El nombre está en un solo lugar, `app_name` en `app/web/views.py`.

**El símbolo ("Flujo")** es una Z hecha de dos trazos iguales girados 180°: uno baja (lo que sale) y el otro sube (lo que entra). La Z es un recorte transparente de un cuadrado redondeado.

- **En las plantillas**, usa el macro `simbolo()` de `app/templates/_logo.html`. Toma el color del texto (`currentColor`), así que se adapta solo al fondo. No lo copies a mano.
- **El nombre va en texto**, en Inter 600, al lado del símbolo, como en la barra lateral y la barra del login.
- **Un solo color:** `--color-text` (`#1d1d1f`), o `#f5f5f7` sobre fondos oscuros. Sin azul ni verde.
- **Tamaño mínimo: 20px.** Por debajo, las dos diagonales se juntan y se pierde el corte. La excepción es el favicon de 16px, donde no hay alternativa.
- **Íconos de archivo** en `app/static/img/`: `favicon.svg` (se aclara en pestañas oscuras), `favicon-32.png` y `apple-touch-icon.png` (180px, a sangre: el sistema aplica la máscara).

## Reglas de color

- `--color-primary` (`#0071e3`) se usa **solo** como relleno del botón primario. Nunca como fondo de sección, texto o icono.
- `--color-link` (`#0066cc`) se usa para enlaces y acciones de texto.
- **Los gastos van en `--color-text` con signo "−"; no en rojo.** El rojo (`--color-danger`) se reserva para presupuestos excedidos, errores y acciones destructivas. Así el rojo conserva su fuerza como alerta y la app no parece estar siempre en problemas.
- Los ingresos van en `--color-income` con signo "+".
- `--color-warning` se usa cuando un presupuesto llega al 80 %.
- Cada color semántico tiene su fondo (`*-bg`). Los dos se usan juntos en avisos y etiquetas de estado.
- `--color-border` es decorativo (1.4:1). Si un borde es lo único que permite ver un control, usa `--color-border-strong`.

## Contraste (WCAG AA: 4.5:1 en texto normal)

| Token | Sobre blanco | Sobre `--color-canvas` |
|---|---|---|
| `--color-text` | 16.8 | 15.5 |
| `--color-text-secondary` | 4.95 | 4.55 |
| `--color-link` | 5.57 | 5.11 |
| `--color-income` | 5.19 | 4.77 |
| `--color-warning` | 5.28 | 4.85 |
| `--color-danger` | 5.38 | 4.94 |
| Blanco sobre `--color-primary` | 4.70 | — |

Los colores de estado también cumplen sobre su propio fondo `*-bg` (4.7:1 o más).

## Números

- **En columnas** (tablas, listas de movimientos, ejes) los montos usan `font-variant-numeric: var(--numeric);` (clase `.num`). Las cifras tabulares tienen el mismo ancho, así que los dígitos quedan alineados.
- **Cifras grandes sueltas** (el saldo total) usan números proporcionales, los normales de la fuente. Con tabulares, en tamaños grandes se ven separadas.

## Gráficas

- Una sola escala por gráfica. Si hay dos medidas distintas (ahorro mensual y saldo acumulado), van en dos gráficas.
- Columnas de máximo 24px, con esquinas de 4px arriba y rectas en la base. Líneas de 2px. Puntos de 8px con un aro de 2px del color de la superficie.
- El periodo actual va en el color fuerte (`--color-income` o `--color-text`) y los anteriores en el suave (`--chart-income-muted`, `--chart-ink-muted`).
- **No usamos colores categóricos.** Verde, naranja y rojo ya significan ingreso, alerta y exceso. Para comparar categorías se usan barras de un solo tono, con la mayor resaltada.
- **Única excepción: los tonos de las cuentas.** Cada cuenta tiene un tono (`--tono-*` en `tokens.css`) que va **solo en el cuadrado de su ícono**, nunca en montos, barras, texto ni fondos de tarjetas. Sirven para reconocer cada cuenta de un vistazo. Son 8 tonos apagados, con trazo de 4.5:1 o más sobre su fondo y lejos del verde de ingreso, el naranja de alerta y el rojo de error (`tests/test_tonos.py` lo comprueba).
- Los estados (alerta, excedido) llevan siempre ícono y texto, nunca solo color.
- Con dos o más series hay leyenda. Con una sola, el título la nombra.
- El texto de las gráficas usa colores de texto, no el color de la serie.
- Las gráficas del dashboard real llevan tooltip al pasar el mouse. La vista previa del login no, porque es decorativa.

## Vidrio líquido

Solo para paneles que **flotan sobre contenido** (como la vista previa del login sobre su fondo de barras): `--glass-bg`, `--glass-blur` y `--glass-edge`. Sobre un fondo plano no aporta nada, porque no hay nada que se vea a través. Es un desvío consciente de la referencia, que es plana; aun así no lleva sombras. Los formularios y las tarjetas de datos principales siguen siendo blancos y sólidos para que se lean bien.

El fondo del login usa además **barras de vidrio verde** (cápsulas translúcidas con brillo en el borde superior). Son decoración, no una gráfica: no tienen ejes ni etiquetas, así que no siguen las reglas de la sección Gráficas. Se eligieron entre cinco variantes (verde sólido, degradado, grafito, azul y vidrio).

## Estructura de la app

Después del login la app es una aplicación con **barra lateral**, no una página larga con scroll: cada función (Resumen, Movimientos, Cuentas, Categorías) está a un clic. La plantilla base es `app/templates/app/base_app.html` y sus estilos están en `app/static/css/app.css`.

- **Barra lateral:** 248px abierta y 76px contraída (solo íconos, con el nombre en `title`). Es blanca, se separa del contenido con una línea de 1px y no tiene sombra. La sección activa lleva una píldora `--color-canvas`.
- **Contraer:** el estado se guarda en la cookie `barra_contraida` para que el servidor pinte la barra ya contraída. Si se guardara en `localStorage`, la barra aparecería abierta un instante en cada página.
- **"Nuevo movimiento"** va arriba en la barra en negro (`btn--ink`), como "Crear cuenta" en el login. El azul queda libre para la acción principal de cada pantalla.
- **Secciones de la Fase 2** (Presupuestos, Metas) aparecen desactivadas con la etiqueta "Fase 2".
- **Barra superior:** título de la sección y sus acciones (por ejemplo, el selector de mes). Es fija y translúcida, como la barra del login.
- **Celular (≤ 760px):** la barra se vuelve un cajón que entra desde la izquierda sobre el contenido. Como flota sobre contenido, es el único lugar de la app con vidrio.
- **Una ruta por sección.** El paso de una a otra lo anima el navegador con View Transitions (`@view-transition`): la barra se queda quieta, la píldora se desliza a la nueva sección y el contenido viejo se desvanece mientras el nuevo entra escalonado (`style="--i: n"`). En Firefox la página cambia sin animación.

## Formularios y diálogos de la app

Los controles nuevos de la sección Movimientos salen de los del login. No agregan colores, radios ni sombras. Están en `app.css` porque el diálogo se usa en todas las secciones.

- **Control segmentado** (`.segmented`): radios nativos ocultos dentro de una píldora `--color-canvas`. La opción elegida es una píldora blanca con `--ring-strong`, el token de "control seleccionado". Se usa para Todos/Ingresos/Gastos en los filtros y para Gasto/Ingreso en el diálogo.
- **Select en píldora** (`.select`, `.select--lg` dentro de formularios): mismo borde, hover y foco que `.float-field__input`, con una flecha propia en SVG.
- **Diálogo** (`.dialog`, un `<dialog>` nativo): tarjeta blanca de 28px **sin sombra** sobre el mismo fondo oscuro del cajón del celular (`rgba(29, 29, 31, 0.18)`). Mide 480px en escritorio y ocupa toda la pantalla en el celular. Los campos, los errores por campo, `.alert--danger` y el botón con spinner y check son los del login. Se cierra con ×, con Esc o haciendo clic en el fondo.
- **Botón destructivo** (`.btn--danger`): fondo `--color-danger`. Solo se usa para confirmar una eliminación. Antes de confirmar, la acción es un botón de texto rojo ("Eliminar movimiento").
- **Aviso** (`.toast`): píldora negra como "Nuevo movimiento", abajo al centro, 4 s, con `role="status"`. Confirma una acción ("Movimiento guardado"), nunca muestra errores; los errores van dentro del formulario.
- **Asistente con IA** (solo si hay `GEMINI_API_KEY`): se marca con el ícono ✦. Cada sección lo usa para una cosa distinta y lo ofrece desde un **menú desplegable de la barra superior** (`.asistente`, manejado por `desplegable.js`): una píldora como el selector de mes que despliega un panel `--color-surface-raised` con el filo del vidrio (`--glass-edge`) y **sin sombra ni transparencia**, porque lleva texto que tiene que leerse sobre cualquier contenido. En el celular el botón queda solo con el ícono y el panel ocupa el ancho de la pantalla.
  - **Movimientos — "✦ Asistente":** registrar con una frase. El botón "Completar" es negro (`btn--ink`), nunca azul, porque el azul queda para "Guardar". Llena el diálogo "Nuevo movimiento" y la persona revisa y guarda; la IA nunca guarda. El mismo bloque aparece en el diálogo (fondo `--color-canvas`, solo al crear).
  - **Resumen — "✦ Analizar mes":** de 1 a 3 observaciones con viñeta y un consejo en un bloque `--color-canvas`. Mientras carga, tres barras grises que laten (esqueleto). Termina con una nota de privacidad que dice qué ve la IA y qué no.
  - **Cuentas:** sin IA en su pantalla, a propósito: saldos, cupos, deudas y pagos son los datos más sensibles. Para registrar con una frase, Gemini solo recibe los nombres de las cuentas.
- **Montos con signo**: el balance y el neto de cada día son verdes con "+" si son positivos o cero, y van en el color del texto con "−" si son negativos. Nunca rojos: el rojo queda para errores y excesos de presupuesto.

## Sección Categorías

- **Dos tarjetas, Gastos e Ingresos**, con lo que sumó cada categoría en el mes del selector, de mayor a menor. Cada fila dice cuántos movimientos tiene y qué parte del total del grupo es. Las que suman $0 van en gris.
- **Cada fila es un enlace** a Movimientos filtrado por esa categoría y ese mes.
- **Predeterminadas y propias:** las predeterminadas son iguales para todos y no se cambian. Las propias llevan un lápiz que abre el diálogo para renombrarlas o eliminarlas. Si en una tarjeta no hay propias, no se reserva el espacio del lápiz.
- **"Nueva categoría"** es la acción principal de la pantalla: botón azul en la barra superior (en el celular, solo el "+").
- **Diálogo:** mismos componentes que el de movimientos (segmentado Gasto/Ingreso, campo flotante, confirmación de eliminar). Si la categoría ya tiene movimientos, el tipo queda fijo con una nota, y para eliminarla hay que elegir a qué categoría del mismo tipo pasarlos ("Pasar y eliminar").

## Sección Cuentas

- **Sin desplazar la página:** arriba, una tarjeta con **Tienes en total** (cifra grande), **Debes en tarjetas** y **Te queda** (verde con "+" o texto con "−"). Debajo, dos columnas: **Dinero | Tarjetas de crédito**. En el celular, una columna con las tarjetas primero, porque tienen fecha límite.
- **Sin selector de mes:** los saldos son de hoy.
- **Íconos de cuenta:** cuadrado de 38px con radio de 12px, ícono de trazo y el tono que eligió la persona (ver Reglas de color).
- **Tarjetas:** deuda con "−" en el color del texto, barra de cupo usado de un solo tono (pista `--color-fill-muted`, relleno `--color-text`), "Disponible $X de $Y" y **"Registrar pago"** en negro (`btn--ink`), porque el azul es de "Nueva cuenta". Con deuda y a 5 días o menos de la fecha límite, la etiqueta va en `--color-warning` sobre su fondo, con texto ("Hoy", "Mañana", "Faltan N días"). Sin deuda dice "Al día". Pasar el cupo es un exceso: "Pasaste el cupo por $X" en rojo.
- **Pagos de tarjeta en Movimientos:** fila en su día con el ícono de la tarjeta, "Desde {cuenta} · No cuenta como gasto" y el monto en gris sin signo. No suman en los totales ni en el neto del día.

## Movimiento

- Duraciones: `--duration-fast` (hover y foco), `--duration-default` (cambios de estado), `--duration-slow` (entradas de paneles).
- Las entradas usan `--ease-emphasized` y se escalonan entre 40 y 90 ms por elemento.
- Todo se desactiva con `prefers-reduced-motion: reduce`: se muestra el estado final al instante.

## Tipografía

Inter se sirve desde `app/static/fonts/` (declarada con `@font-face` en `styles.css`), no desde Google Fonts: carga sin internet y no envía datos a terceros.

Inter no se precarga (`<link rel="preload">`): en móvil competía con el CSS y retrasaba el primer pintado. Mientras baja se ve "Inter Fallback", Arial ajustada con `size-adjust` y `ascent-override` a las medidas de Inter, para que el texto no salte al cambiar de fuente. `inter-latin.woff2` está recortada (receta en `app/static/fonts/README.md`).

Inter va **primera** en la lista de fuentes. Si se pone `-apple-system` o `BlinkMacSystemFont` antes, Chrome en Linux (comprobado; posiblemente también en Windows) los toma como "fuente del sistema" y nunca llega a usar Inter.

`--font-display` va en títulos de 21px o más y `--font-text` en todo lo demás.

## No hacer

- Sombras en tarjetas, botones o modales.
- Degradados.
- Radios distintos a los definidos (nada de 8px ni 12px en tarjetas).
- Peso 700.
- Más de un color de acento en la misma vista.
