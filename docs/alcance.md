# Alcance del proyecto: Gestión de Finanzas Personales

> Documento en discusión. Las secciones marcadas como **Decisiones pendientes** las debe cerrar el equipo.

## Idea central

Aplicación web donde una persona registra sus ingresos y gastos, ve en qué se le va el dinero y se pone límites y metas.

## Fase 1: MVP

Lo mínimo para tener una aplicación funcional.

| Módulo | Descripción |
|---|---|
| **Usuarios** | Registro e inicio de sesión. Se incluye desde el inicio para que todas las tablas tengan `usuario_id` desde el principio. |
| **Cuentas** | Efectivo, cuenta bancaria, tarjeta, etc. Cada cuenta tiene un saldo inicial. |
| **Categorías** | Comida, transporte, arriendo, salario, etc. Cada una es de tipo *ingreso* o *gasto*. Existen categorías por defecto y el usuario puede crear las suyas. |
| **Movimientos** | Monto, tipo (ingreso/gasto), fecha, categoría, cuenta y nota opcional. Se pueden crear, editar y eliminar. |
| **Dashboard** | Saldo total, ingresos vs. gastos del mes y gráfica de gastos por categoría. |
| **Historial** | Lista de movimientos con filtros por fecha, categoría, cuenta y tipo. |

## Fase 2: Funcionalidades de valor

- **Presupuestos mensuales por categoría** (ej. "máximo 400.000 en comida") con alerta al 80 % y al superar el 100 %.
- **Metas de ahorro** (ej. "viaje: 2.000.000 para diciembre") con barra de progreso.
- **Movimientos recurrentes** (arriendo, suscripciones, salario) que se registran automáticamente cada mes.
- **Transferencias entre cuentas** (ej. banco → efectivo) que no cuentan como gasto.

## Fase 3: Extras (si hay tiempo)

- Exportar historial a CSV/PDF.
- Calendario de pagos próximos.
- Análisis con la regla 50/30/20 (necesidades / gustos / ahorro).
- Comparación del mes actual contra el anterior.
- Modo oscuro.

## Modelo de datos (borrador)

```
Usuario       (id, nombre, email, password_hash, creado_en)
Cuenta        (id, usuario_id, nombre, tipo, saldo_inicial)
Categoria     (id, usuario_id | null, nombre, tipo: ingreso|gasto)
Movimiento    (id, usuario_id, cuenta_id, categoria_id, tipo, monto, fecha, nota)

-- Fase 2
Presupuesto   (id, usuario_id, categoria_id, monto_limite, mes, anio)
MetaAhorro    (id, usuario_id, nombre, monto_objetivo, monto_actual, fecha_limite)
Recurrente    (id, usuario_id, cuenta_id, categoria_id, tipo, monto, dia_del_mes, activo)
Transferencia (id, usuario_id, cuenta_origen_id, cuenta_destino_id, monto, fecha)
```

`Categoria.usuario_id = null` indica una categoría por defecto del sistema.

## Reglas de negocio (capa `services/`)

Estas reglas viven en los servicios y se cubren con pruebas unitarias en Pytest:

- Saldo de una cuenta = saldo inicial + ingresos − gastos ± transferencias.
- El monto de un movimiento siempre es mayor que 0.
- Un gasto no puede usar una categoría de ingreso, ni al revés.
- No se puede eliminar una categoría con movimientos asociados (o se reasignan; **por decidir**).
- El porcentaje de presupuesto consumido en el mes se calcula en el backend.

**Nota técnica:** el dinero se guarda como `Decimal` (`Numeric` en SQLAlchemy) o como entero en centavos, nunca como `float`, para evitar errores de redondeo.

## Pantallas (Frontend)

1. Login y registro.
2. Dashboard: tarjetas de resumen y gráficas (propuesta: Chart.js, liviano y sin paso de build).
3. Movimientos: lista con filtros y formulario/modal rápido para registrar.
4. Cuentas.
5. Categorías.
6. Presupuestos y metas (Fase 2).

## Decisiones pendientes

- [ ] **Moneda:** ¿una sola fija o configurable por usuario?
- [ ] **Autenticación:** ¿sesión con cookie (más simple con Jinja2) o JWT?
- [ ] **Tiempo disponible:** define si la Fase 2 entra en la entrega.
- [ ] **Nombre de la app:** `app/main.py` todavía dice "bibliopedia".
- [ ] **Eliminación de categorías con movimientos:** bloquear o reasignar.
