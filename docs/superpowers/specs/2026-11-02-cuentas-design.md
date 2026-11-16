# Diseño: sección Cuentas

Fecha: 2026-11-02 · Rama: `feature/cuentas` (sale de `feature/categorias`, PR #7)

En este documento, **(decisión de Juan)** marca lo que decidió el usuario en la conversación. **(propuesta)** marca lo que propuso quien escribe el documento y Juan aprobó el 2026-11-02. **(decisión técnica)** marca lo que se resolvió después de la revisión del documento y Juan no revisó uno por uno.

## Intención

Hoy `/cuentas` es una página "en construcción". Las tres cuentas de la app (Cuenta de ahorros, Billetera digital y Efectivo) son fijas, y el "Saldo total" del Resumen sale de cifras escritas a mano en `app/services/dashboard.py`.

La persona tiene la plata repartida entre Nequi, Nu, efectivo y cuentas de ahorros de varios bancos, y además tiene tarjetas de crédito con cupo y deuda. Lo que quiere saber es **cuánto dinero tiene en total entre todas sus cuentas** y, en las tarjetas, **cuánto debe y hasta cuándo puede pagar**.

**Éxito:** al abrir Cuentas, sin desplazarse por la página, se responde "¿cuánto tengo?", "¿cuánto debo?" y "¿qué tarjeta tengo que pagar pronto?". Registrar el pago de una tarjeta toma unos segundos y deja bien los saldos de las dos cuentas.

## Objetivos

1. Crear, editar y eliminar cuentas de **dinero** (ahorros, corriente, billetera digital, efectivo) y **tarjetas de crédito**.
2. Que el saldo de cada cuenta sea real: se calcula con lo que tenía al crearla y los movimientos registrados después.
3. Tarjetas de crédito con **cupo**, **deuda**, **disponible** y **fecha límite de pago** (decisión de Juan).
4. **Registrar un pago de tarjeta:** cuánto se paga y desde qué cuenta de dinero (decisión de Juan).
5. Un total arriba: **Tienes**, **Debes** y **Te queda**.
6. Que el Resumen muestre el saldo real.
7. Un contrato estable (esquemas, servicio y API JSON) para que el backend solo cambie las consultas, igual que en las otras secciones.

## Fuera de alcance

- **Transferencias generales entre cuentas**, por ejemplo del banco a efectivo. Siguen en la Fase 2 (decisión de Juan: "por ahora sin registrar las transferencias"). El pago de tarjeta es el único movimiento de dinero entre cuentas en esta entrega.
- Fecha de corte, pago mínimo, intereses, compras a cuotas y extractos.
- Varias monedas: todo es en pesos colombianos.
- Logos reales de bancos, porque son marcas registradas.
- IA en esta sección. Se deja sin IA a propósito, como ya dice `app/services/ia.py`.
- Conectarse con los bancos para traer los saldos automáticamente.

## Anti-objetivos (sería un fracaso aunque funcione)

- Tener que bajar en la página para ver el total y las tarjetas en una pantalla de escritorio normal (≥ 1280 × 800) con hasta unas 5 cuentas y 3 tarjetas (decisión de Juan: evitar al máximo el desplazamiento).
- Que un pago de tarjeta cuente como gasto o como ingreso en Movimientos, en el Resumen o en el análisis de la IA. La compra ya se contó cuando se pagó con la tarjeta.
- Que el Resumen y Cuentas muestren saldos distintos.
- Que una deuda se vea como plata disponible: el total "Tienes" nunca suma tarjetas.
- Que la pantalla se aleje del sistema de diseño más allá de la excepción de color de los íconos (ver "Íconos y tonos").

## Restricciones

- **Mismo stack:** FastAPI + Jinja2 renderizado en el servidor, CSS propio con `tokens.css` y JS sin librerías ni paso de build. Seguir los patrones de Movimientos y Categorías: servicio en memoria con `TODO(backend)`, API JSON con errores `{"errores": {campo: mensaje}}` y diálogo `<dialog>` con errores por campo.
- **Dinero:** siempre `Decimal`. Los montos se guardan positivos y el tipo dice si suma o resta.
- **Sistema de diseño:** `docs/design-system.md`. Los gastos y las deudas van en el color del texto con "−", nunca en rojo. El rojo es solo para errores y para el exceso de cupo.
- **Usuario:** `USUARIO_DEMO`, mientras no exista el login real.
- **Datos de prueba que se siembran por mes:** `services/movimientos.py` siembra cada mes la primera vez que se pide. El saldo depende de todos los meses desde que se creó la cuenta, así que al calcular saldos hay que sembrar esos meses antes. Si no, el saldo cambiaría según los meses que se hayan visitado.

## Modelo

```
Cuenta (id, usuario_id, nombre, tipo, icono, tono, creada_en, saldo_inicial | deuda_inicial, cupo, dia_pago)
PagoTarjeta (id, usuario_id, tarjeta_id, cuenta_origen_id, monto, fecha)
```

- `tipo`: `ahorros`, `corriente`, `billetera` o `efectivo` (cuentas de **dinero**), o `tarjeta` (tarjeta de crédito).
- Las cuentas de dinero tienen `saldo_inicial`. Las tarjetas tienen `deuda_inicial`, `cupo` y `dia_pago` (día del mes, de 1 a 31).
- **Saldo de una cuenta de dinero** = saldo inicial + ingresos − gastos − pagos de tarjeta que salieron de ella.
- **Deuda de una tarjeta** = deuda inicial + gastos − ingresos − pagos recibidos. Un ingreso a una tarjeta es una devolución.
- **Disponible** = cupo − deuda. Si da negativo, la tarjeta pasó su cupo (ver Pantalla).
- **Qué movimientos cuentan (propuesta):** solo los que tienen fecha igual o posterior a `creada_en`. Lo que se escribe al crear la cuenta es su saldo (o su deuda) **de hoy**, y ese número ya incluye todo lo anterior. Así, registrar un gasto viejo no descuadra el saldo. Al crear la cuenta, el campo se llama "Saldo de hoy" (o "Deuda de hoy") para que esto se entienda.
- `creada_en` no se edita (propuesta).

## Pantalla (opción A del boceto, decisión de Juan)

Boceto: `.superpowers/brainstorm/110813-1793644483/content/cuentas-pantalla.html`, opción A.

### Barra superior

- Título "Cuentas" y el botón azul **"Nueva cuenta"** (`btn--primary`, solo "+" en el celular), como "Nueva categoría".
- **Sin selector de mes (propuesta):** los saldos son de hoy, no de un mes.

### Totales

Una `.card` con tres cifras en fila:

- **Tienes en total:** la suma de los saldos de las cuentas de dinero. Es la cifra grande (`.big`).
- **Debes en tarjetas:** la suma de las deudas, con "−".
- **Te queda:** lo que tienes menos lo que debes, verde con "+" si es positivo o cero, y en el color del texto con "−" si es negativo. Es la misma regla de los montos con signo.

Si no hay tarjetas, solo se muestra "Tienes en total".

### Dos columnas: Dinero | Tarjetas de crédito

**Dinero:** una fila por cuenta (`.rows`) con su ícono, el nombre, el tipo debajo (por ejemplo "Cuenta de ahorros") y el saldo a la derecha. Un saldo negativo va con "−" en el color del texto. Tocar la fila abre el diálogo para editarla (propuesta: así se hace en Categorías con el lápiz, pero aquí todas las cuentas son propias y editables, así que la fila entera abre el diálogo).

**Tarjetas de crédito:** una fila por tarjeta, ordenadas por fecha límite más cercana (propuesta). Cada fila tiene:

- El ícono, el nombre y "Pagar antes del 15 nov", con una etiqueta de los días que faltan.
- La deuda a la derecha (−$840.000).
- Una barra del cupo usado: un solo tono, como las barras de categorías.
- "Disponible $2.160.000 de $3.000.000" y el botón negro **"Registrar pago"** (`btn--ink`, porque el azul queda para "Nueva cuenta").

**Fecha límite (propuesta):** es la próxima vez que llega `dia_pago`: este mes si todavía no ha pasado, o el siguiente. Si el mes tiene menos días, se usa su último día.

- Con deuda y 5 días o menos: etiqueta de alerta (`--color-warning` con su fondo y texto, nunca solo color).
- Sin deuda: "Al día" en lugar de la fecha.
- Si la deuda pasa el cupo: "Pasaste el cupo por $X" en rojo (`--color-danger`). Es un exceso, como el de un presupuesto.

**Sin cuentas:** si la persona no tiene ninguna cuenta, se muestra el estado vacío de siempre (ícono, texto y "Crear una cuenta"). Si no tiene tarjetas, la columna de tarjetas muestra un texto corto con "Agregar tarjeta".

**Celular (≤ 760px):** una sola columna con Totales, luego Tarjetas (porque tienen fecha límite) y luego Dinero (propuesta).

### Íconos y tonos (opción B del boceto, decisión de Juan)

Boceto: `cuentas-iconos.html`, opción B.

- Cada cuenta tiene un **ícono** y un **tono suave**, y los dos se eligen al crearla.
- **Íconos:** un juego de unos 8 de trazo, en el mismo estilo de `_iconos.html`: banco, alcancía, billetera, celular, billetes, tarjeta, monedas y maletín. El ícono por defecto depende del tipo.
- **Tonos:** unos 8 apagados. Cada uno es un fondo claro y un color de trazo oscuro del mismo tono, y el trazo tiene que cumplir 4.5:1 sobre su fondo. El ícono va en un cuadrado de 38px con radio de 12px.
- **Excepción al sistema de diseño:** el documento de diseño dice "no usamos colores categóricos" para que verde, naranja y rojo conserven su significado. Los tonos se permiten **solo en el ícono de una cuenta**, nunca en montos, barras, texto ni fondos de tarjetas. Hay que anotar esta excepción en `docs/design-system.md`. Los tonos no pueden parecerse al verde de ingreso, al naranja de alerta ni al rojo de error, o hay que dejar claro que no significan eso.

### Diálogo "Nueva cuenta" / "Editar cuenta"

- **Tipo**, en un segmentado de dos opciones: **Dinero** o **Tarjeta de crédito**. Con Dinero aparece un select con la clase: ahorros, corriente, billetera digital o efectivo.
- **Nombre**: obligatorio, de hasta 40 caracteres y único entre las cuentas de la persona, sin distinguir tildes ni mayúsculas.
- **Ícono y tono**: dos filas de opciones como radios visuales, con una vista previa del ícono.
- Si es de **Dinero**: "Saldo de hoy", de 0 o más.
- Si es **Tarjeta**: "Cupo" (mayor que 0), "Deuda de hoy" (0 o más) y "Día límite de pago" (de 1 a 31).
- El tipo (dinero o tarjeta) no cambia si la cuenta ya tiene movimientos o pagos (propuesta, igual que en Categorías).
- **Al editar**, el campo "Saldo de hoy" (o "Deuda de hoy") **trae el saldo calculado y se puede cambiar** (decisión de Juan). Así se corrige un error al crear la cuenta o una diferencia con el banco. Si se cambia, el servicio ajusta `saldo_inicial` (o `deuda_inicial`) en la diferencia, para que el saldo calculado quede igual a lo escrito. No es un movimiento, no deja historial y no cuenta como gasto ni como ingreso. Debajo del campo, una nota: "Si no coincide con tu banco, escribe el saldo real".
- Desde aquí también se elimina la cuenta (ver Reglas).

### Diálogo "Registrar pago" (decisión de Juan)

Boceto: la parte de abajo de `cuentas-pantalla.html`.

- El título es "Pagar Tarjeta Nu" y debajo dice cuánto debes y la fecha límite.
- **Monto**: es el campo de dinero de "Nuevo movimiento". Viene lleno con la deuda completa y hay un botón "Pagar todo" (propuesta).
- **Desde**: un select solo con las cuentas de dinero, cada una con su saldo.
- **Fecha**: hoy por defecto, y no puede ser futura.
- Debajo del botón, una línea que muestra cómo quedan las dos cuentas después del pago.
- Al guardar se recarga la página con el aviso "Pago registrado".
- **Editar o eliminar un pago:** se hace desde su fila en Movimientos (ver abajo). Se usa este mismo diálogo en modo edición, con "Eliminar pago" y una confirmación, igual que en los movimientos.

## Reglas (servicio)

- **Pago:** el monto tiene que ser mayor que 0 y **no puede pasar la deuda** ("Debes $840.000"). La cuenta de origen tiene que ser de dinero y **le tiene que alcanzar** ("Nequi tiene $525.000") (propuesta). La fecha no puede ser futura ni anterior a la creación de cualquiera de las dos cuentas.
- **Movimientos:** no se bloquean por falta de saldo. Una cuenta de dinero puede quedar en negativo si la persona registra un gasto mayor a su saldo, y una tarjeta puede pasar su cupo. Se muestra, pero no se impide (propuesta).
- **Eliminar una cuenta sin movimientos ni pagos:** se elimina directamente.
- **Eliminar una cuenta con movimientos o pagos (propuesta, igual que en Categorías):** primero hay que pasar todo a otra cuenta del mismo grupo (dinero a dinero, tarjeta a tarjeta). Los pagos también se pasan: los de una tarjeta a la otra tarjeta, y los de una cuenta de origen a la otra cuenta.
- **Movimientos y pagos pasados a una cuenta más nueva** (decisión técnica, después de la revisión final): los que tienen fecha anterior a la `creada_en` de la cuenta destino se ven en su lista, pero no cambian su saldo, por la misma regla de `creada_en`. Un pago así se puede seguir editando: la deuda o el saldo solo se revisan en las cuentas que el pago sí mueve, y la fecha contra la creación solo si cambia.
- **Si es la única cuenta de su grupo y tiene movimientos o pagos** (decisión técnica), no se deja eliminar: "Es tu única tarjeta. Crea otra para pasarle sus movimientos antes de eliminarla." (o "tu única cuenta de dinero"). Nunca se borran movimientos al eliminar una cuenta.
- **Cuentas de prueba del usuario demo (decisión técnica):**
  - La plantilla mensual de `services/movimientos.py` **no cambia**, para que Movimientos, Categorías y la IA den las mismas cifras de hoy.
  - El demo empieza con las tres cuentas de hoy (Cuenta de ahorros, Billetera digital y Efectivo), que ahora se pueden editar, y una "Tarjeta de crédito" con cupo de $3.000.000, deuda de $840.000 y día de pago 15. La plantilla no tiene compras con tarjeta, así que su deuda solo cambia con lo que registre la persona.
  - `creada_en` de las cuentas demo es **el primer día del mes anterior a `hoy()`**. Así solo cuentan uno o dos meses de la plantilla y ninguna cuenta queda en negativo. Los saldos iniciales se eligen para que el mes actual se vea parecido a las cifras de hoy (unos $3.600.000, $525.000 y $245.500). Las pruebas fijan `hoy()`, así que las cifras son siempre las mismas.
  - Las cifras del Resumen cambian. Hay que actualizar las pruebas que dependen de los saldos escritos a mano.

## Cambios en otras secciones

- **Nuevo movimiento y filtros de Movimientos:** el select de cuenta se agrupa en "Dinero" y "Tarjetas" con `<optgroup>`. Un gasto con tarjeta es una compra y un ingreso a una tarjeta es una devolución.
- **Pagos de tarjeta en Movimientos (decisión de Juan):** cada pago aparece en la lista, en su día, como una fila más:
  - Ícono de la tarjeta, "Pago Tarjeta Nu" y debajo "Desde Ahorros Banco X · No cuenta como gasto". El monto va en gris y sin signo.
  - No suma en los totales de arriba (Ingresos, Gastos, Balance) ni en el neto del día.
  - Filtros: con "Todos" se ven. Con "Gastos" o "Ingresos" no se ven. Con un filtro de cuenta se ven si la tarjeta o la cuenta de origen es esa. Con un filtro de categoría no se ven. La búsqueda encuentra "pago" y el nombre de las dos cuentas.
  - Al tocar la fila se abre el diálogo de pago en modo edición, con "Eliminar pago".
  - La tarjeta *Recientes* del Resumen sigue mostrando solo movimientos, sin pagos (decisión técnica).
  - Cómo se mezclan las dos listas por día (por ejemplo, `ListaMovimientos` con una lista `pagos` aparte) queda para quien construye.
- **Resumen (propuesta):** "Saldo total" pasa a ser el "Tienes en total" real, y en la línea de abajo dice "Debes $X en tarjetas · Ver cuentas" cuando hay deuda. `services/dashboard.py` deja de tener saldos escritos a mano y usa el servicio de cuentas.
- **IA (decisión de Juan):** el análisis del mes sigue sin ver cuentas ni saldos. La función de registrar con una frase **sigue mandándole a Gemini solo los nombres de las cuentas**, para entender frases como "pagué con Nequi". Nunca le manda saldos, cupos, deudas, fechas de pago ni pagos. El asistente no registra pagos de tarjeta, y si sugiere una tarjeta para un gasto es una compra normal. Hay que corregir el docstring de `app/services/ia.py`, que hoy dice que los nombres de bancos nunca salen, y agregar una prueba que compruebe que en el prompt no aparece ningún saldo.
- **Pagos fuera de los totales:** los pagos de tarjeta no aparecen en los ingresos ni en los gastos de Movimientos, del Resumen ni del análisis.

## Contrato (orientativo, el detalle queda para quien construye)

- `app/schemas/cuentas.py`: `Cuenta`, `CuentaEntrada`, `CuentaConSaldo` (saldo o deuda, disponible y fecha límite) y `PanelCuentas` (totales, dinero y tarjetas). Además `PagoEntrada` y `Pago`.
- `app/services/cuentas.py`: `listar`, `obtener`, `crear`, `actualizar`, `eliminar(mover_a)`, `panel(usuario_id)` y `registrar_pago`. `movimientos.catalogo()` pasa a tomar las cuentas de aquí, como ya hace con las categorías.
- API: `/api/v1/cuentas` (GET, POST, PUT, DELETE `?mover_a=`), `POST /api/v1/cuentas/{id}/pagos` y `PUT`/`DELETE /api/v1/pagos/{id}`. Al editar un pago se vuelven a validar sus reglas, sin contar el monto anterior del mismo pago.
- Pruebas: reglas del servicio (saldos, deuda, disponible, fecha límite en meses cortos y en diciembre, límites del pago, eliminar pasando los movimientos), API y página. Hay que actualizar las pruebas actuales que dependen de los saldos de prueba del Resumen.

## Queda para quien construye

- La forma exacta de los esquemas, los nombres de las funciones y cómo se organizan los archivos.
- Los dibujos de los íconos y los valores de los tonos, siempre que cumplan el contraste y la regla de no parecerse a los colores de estado.
- Los textos de los mensajes de error, siguiendo el tono de los que ya hay.
- Cómo se ve el estado vacío.
