# Metas de ahorro

## Intención

Es la sección Metas de la Fase 2 (`docs/alcance.md`): «viaje: 2.000.000 para diciembre», con barra de
progreso. Juan eligió que la plata entre registrando **aportes en la meta** (opción 1). Es plata
apartada en la cabeza de la persona: no sale de ninguna cuenta ni cuenta como gasto. Además de
mostrar el progreso, cada meta dice **cuánto guardar por mes** para llegar a la fecha y si va al día.

## Metas, no metas y antimetas

- **Metas:**
  - Crear, editar y eliminar metas.
  - Aportar y retirar plata, con historial.
  - Ver el progreso, lo que falta, cuánto guardar por mes y el estado de cada meta.
- **No metas:**
  - Mover plata entre cuentas.
  - Que las metas aparezcan en el Resumen o en Cuentas.
  - Recordatorios.
  - Metas compartidas.
- **Antimetas:**
  - Que un aporte cambie el saldo de una cuenta o los ingresos y gastos del mes.
  - Que una persona vea las metas de otra.

## Enfoques

1. **Aportes registrados en la meta (elegido).** Es lo más simple de entender y de presentar.
2. El aporte sale de una cuenta, como el pago de una tarjeta. Descartado: baja «Tienes» aunque la
   plata siga siendo de la persona.
3. Meta ligada al saldo de una cuenta. Descartado: exige una cuenta por meta.

## Diseño

*Todo lo que sigue es decisión mía, sobre lo que Juan eligió.*

**Datos**
- `MetaDB(id, usuario_id, nombre, objetivo, fecha_limite | null, creada_en)`.
- `AporteMetaDB(id, usuario_id, meta_id, monto, fecha)`: el monto es positivo para un aporte y
  negativo para un retiro.
- Lo ahorrado se calcula sumando los aportes; no se guarda aparte, así nunca se descuadra. El
  `monto_actual` del alcance es esa suma.

**Reglas**
- **Nombre:** obligatorio, de hasta 40 caracteres y único por persona, sin importar tildes ni
  mayúsculas.
- **Objetivo:** mayor que 0 y menor que `MAX_MONTO`.
- **Fecha límite:** opcional. Al crearla o cambiarla, debe ser de hoy en adelante.
- **Máximo:** 20 metas por persona.
- **Aporte o retiro:**
  - El monto es mayor que 0 y menor que `MAX_MONTO`.
  - La fecha no puede ser futura ni anterior a la creación de la meta.
  - No se puede retirar más de lo ahorrado.
- **Borrar un aporte:** se permite, salvo que lo ahorrado quede negativo.
- **Eliminar una meta:** borra también sus aportes, con confirmación.

**Cálculos**
- Faltante: `max(objetivo − ahorrado, 0)`. Porcentaje: `ahorrado / objetivo`, con la barra topada en
  100 %.
- **Cuánto guardar por mes:**
  - Solo si hay fecha límite, la meta no está cumplida y la fecha no pasó.
  - Meses restantes = meses desde el mes actual hasta el de la fecha límite, ambos incluidos.
  - Por mes = faltante ÷ meses restantes, redondeado hacia arriba al peso.
- **Estado:**
  - `cumplida`: ahorrado ≥ objetivo.
  - `sin_fecha`: no tiene fecha límite.
  - `vencida`: la fecha límite ya pasó.
  - `atrasada`: lo ahorrado es menor que lo esperado a hoy. Lo esperado es el objetivo × (días desde
    la creación ÷ días totales).
  - `al_dia`: en cualquier otro caso.
- **Orden:** primero las que no están cumplidas, por fecha límite (las que no tienen fecha van al
  final); después las cumplidas.

**API** (todas con sesión, como el resto)
- `GET` y `POST /api/v1/metas`.
- `PUT` y `DELETE /api/v1/metas/{id}`.
- `POST /api/v1/metas/{id}/aportes`, con `{monto, fecha, retiro}`.
- `DELETE /api/v1/metas/{id}/aportes/{aporte_id}`.

**Página `/metas`**
- La sección sale de «Próximamente» y entra al menú después de Presupuestos.
- Arriba, el total ahorrado en las metas.
- Una tarjeta por meta:
  - Nombre y estado.
  - «$X de $Y» y la barra de progreso.
  - Lo que falta y cuánto guardar por mes hasta la fecha.
  - Los botones «Aportar» y «Retirar».
  - Los últimos aportes, cada uno con su botón para borrarlo.
- Al tocar el nombre se edita la meta.
- Sin metas, se ve el estado vacío con «Crear una meta».
- Diálogos:
  - Meta: nombre, objetivo, fecha límite opcional y eliminar.
  - Aporte: Aportar o Retirar, monto y fecha.
  - Siguen el patrón de Cuentas.
