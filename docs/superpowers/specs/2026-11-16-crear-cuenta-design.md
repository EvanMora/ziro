# Crear una cuenta y seguridad de usuarios

## Intención

Hoy Ziro tiene un login que no protege nada. Las páginas y la API funcionan sin iniciar sesión, todas
las rutas trabajan con el usuario fijo `USUARIO_DEMO` (id 1), las contraseñas se guardan con SHA-256
sin sal y no existe la pantalla para crear una cuenta (`/registro` da 404). Juan quiere que cualquier
persona pueda crear su cuenta y que la seguridad de los usuarios quede impecable: contraseñas bien
cifradas, cada quien solo ve y toca sus propios datos, y nada de datos de demostración en la app.

Es un proyecto de curso, pero la seguridad se hace como si fuera para usuarios reales. Juan autorizó
explícitamente cambiar el backend de Evan para esto, y hay que avisarle a Evan (mensaje aparte).

## Metas

1. Pantalla `/registro` con el mismo diseño del login, que crea la cuenta y deja a la persona dentro.
2. Contraseñas con Argon2id. Los hashes SHA-256 que ya existan se actualizan solos al iniciar sesión.
3. Validación en el servidor del registro y del login, no solo en el navegador.
4. Cada página y cada endpoint usan el usuario de la sesión. Sin sesión, las páginas llevan a `/login` y
   la API responde 401. Nadie puede leer ni cambiar datos de otro usuario aunque adivine un id.
5. Sesión segura: se renueva al entrar, cookie protegida, vence según «Recordarme», «Cerrar sesión»
   en la app.
6. Límite de intentos en login y registro.
7. Sin demo: la app nunca siembra datos de prueba. Una cuenta nueva empieza con las 7 categorías
   predeterminadas y nada más.
8. Se quita el enlace «¿Olvidaste tu contraseña?» del login.

## No metas

- Recuperar la contraseña o verificar el correo (no hay envío de correos; Juan lo descartó).
- Iniciar sesión con Google (las columnas existen, pero no hay rutas; queda como está).
- Cambiar contraseña, editar perfil o borrar cuenta.
- Migraciones con Alembic, persistencia en Docker y el nombre del archivo `usuarios.sqlite` (son
  pendientes de Evan que no son de seguridad).
- Diseñar pantallas de bienvenida para cuentas vacías. Si una pantalla se rompe o queda confusa sin
  datos, se arregla lo mínimo para que funcione.

## Antimetas

- Que algún camino (página, API, IA) siga usando un usuario fijo o deje ver datos ajenos.
- Que el registro se vea o se comporte distinto del login.
- Romper los tests existentes en vez de adaptarlos: las cifras que comprueban deben seguir siendo las
  mismas.

## Enfoques

- **A. Página propia `/registro` con el diseño del login.** Elegido por Juan: los enlaces ya apuntan
  ahí, reutiliza el CSS y el comportamiento del login y el botón «atrás» funciona.
- B. Voltear la tarjeta del login entre «Iniciar sesión» y «Crear cuenta». Descartado: dos formularios
  en una página, enlaces por cambiar y la URL no cambia.

Para la demo, Juan eligió **no tener demo** frente a un botón «Probar la demo» o una cuenta demo con
contraseña.

## Diseño

### 1. Pantalla de registro

- `GET /registro` en `app/web/views.py`, con el mismo contexto del login (`year`, `preview`).
- El encabezado, el hero, la vista previa decorativa y el pie salen de `login.html` a una plantilla
  base común (*mi decisión*). `login.html` y `registro.html` solo cambian la acción del encabezado y la
  tarjeta.
- Encabezado del registro: «¿Ya tienes cuenta? · Iniciar sesión».
- La tarjeta, con textos que son *mi decisión*:

```
        [Z dibujada]
   Crea tu cuenta
   Empieza a ordenar tu dinero en un minuto.

   [👤 Nombre                 ]
   [✉  Correo electrónico      ]
   [🔒 Contraseña           👁 ]
       Mínimo 8 caracteres.
   [      Crear cuenta        ]

   ¿Ya tienes cuenta?
   [      Iniciar sesión      ]
```

- Campos: nombre, correo y contraseña. Sin «confirmar contraseña», porque el ojo permite revisarla.
- La validación del navegador repite las reglas del servidor (sección 3), para responder al instante.
- `POST /api/v1/auth/registro`:
  - **201:** spinner, check y luego `/resumen`.
  - **422 `{"errores": {...}}`:** cada mensaje bajo su campo, sacudida y foco en el primer error.
  - **429:** aviso de demasiados intentos.
  - **Sin conexión u otro error:** aviso general.
- JS (*mi decisión*): lo que comparten el login y el registro (errores por campo, aviso, spinner,
  check, sacudida, ojo y Bloq Mayús) sale de `login.js` a un módulo común. Cada página trae un script
  corto con su validación y su respuesta.
- En el login se quita «¿Olvidaste tu contraseña?» y «Recordarme» queda solo en esa fila.
- Si ya hay sesión, `/login` y `/registro` llevan a `/resumen`.

### 2. Contraseñas

- Argon2id con `argon2-cffi` (`PasswordHasher` con sus parámetros por defecto, que son los
  recomendados por OWASP). La sal va dentro del hash.
- Hashes viejos: si el hash guardado no empieza por `$argon2`, se compara como SHA-256 con
  `hmac.compare_digest`. Si coincide, se guarda de nuevo con Argon2id en ese mismo momento. Lo mismo
  si `check_needs_rehash` dice que los parámetros cambiaron.
- Si el correo no existe o la cuenta no tiene contraseña, se verifica contra un hash Argon2 fijo para
  que la respuesta tarde lo mismo y no revele qué correos existen.
- Las contraseñas nunca se registran en logs ni se devuelven en respuestas.

### 3. Validación en el servidor

Las reglas viven en `app/services/usuarios.py` y los errores salen como `ErrorValidacion` por campo,
en español y con el tono del login:

- **Nombre:** se limpia de espacios. Obligatorio, de 1 a 100 caracteres.
- **Correo:** se limpia de espacios y se pasa a minúsculas. Hasta 254 caracteres y con formato válido
  (`email-validator`, que ya viene con `fastapi[standard]`, sin consultar DNS). Único sin importar
  mayúsculas: la búsqueda compara en minúsculas, así que un correo viejo guardado con mayúsculas
  también se encuentra.
- **Contraseña:** de 8 a 128 caracteres. El tope evita que alguien mande contraseñas enormes para
  gastar CPU.
- **Login:** el correo se normaliza igual. Correo o contraseña malos dan el mismo 401 y el mismo
  mensaje.

### 4. Sesión

- La cookie `SessionMiddleware` guarda solo `usuario_id` y `expira` (timestamp).
- Al registrarse o iniciar sesión se borra la sesión anterior antes de escribir la nueva (contra la
  fijación de sesión).
- **«Recordarme»:** `expira` = ahora + 30 días; sin marcar, ahora + 12 horas (*mi decisión*). La
  cookie se configura con `max_age` de 30 días, y quien comprueba el vencimiento es el servidor.
- La cookie es `HttpOnly` (la pone Starlette), `SameSite=Lax`, y `Secure` cuando
  `ENVIRONMENT=production`.
- **`SECRET_KEY`:** en producción la app no arranca sin ella o si mide menos de 32 caracteres. En
  desarrollo, si falta, se genera una al azar por proceso con un aviso en consola (se cierran las
  sesiones al reiniciar). Se quita el valor fijo `desarrollo-inseguro-cambiar`.
- **Cerrar sesión:** opción en el menú del usuario de la barra lateral (`base_app.html`). Hace
  `POST /api/v1/auth/logout`, que ya existe, y lleva a `/login`.

### 5. Autorización: cada quien sus datos

- Una sola dependencia de FastAPI, `usuario_actual`, en `app/web/sesion.py` (que reemplaza a
  `USUARIO_DEMO`). Lee la sesión, revisa `expira`, carga el usuario de la base y devuelve los datos de
  la sesión (id, nombre, correo, iniciales).
  - Si no hay sesión, venció o el usuario ya no existe, limpia la sesión y lanza una excepción propia.
  - Un manejador en `app/main.py` la responde con **303 a `/login`** en las páginas y con **401
    `{"detail": "Inicia sesión para continuar."}`** en `/api/`.
- La usan todas las páginas de `views.py`, todos los routers de `app/api/` (categorías, cuentas,
  pagos, movimientos, presupuestos, ia) y la raíz `/`, que lleva a `/resumen` con sesión y a `/login`
  sin ella. Quedan públicas solo `/login`, `/registro`, `/static` y `POST` de registro, login y logout.
- La barra lateral muestra el nombre, el correo y las iniciales del usuario de la sesión.
- Los servicios ya filtran por `usuario_id` en cada consulta y validan que la cuenta y la categoría de
  un movimiento sean del usuario. Se agregan tests de aislamiento entre dos usuarios: B no ve ni
  edita ni borra cuentas, movimientos, categorías, pagos ni presupuestos de A usando sus ids, y no
  puede usarlos dentro de los suyos (p. ej. un movimiento de B con una cuenta de A da 422).
- Con `PRAGMA foreign_keys=ON` en cada conexión SQLite, las claves foráneas se cumplen de verdad. Por
  eso, al eliminar una categoría propia se borran sus presupuestos en la misma transacción (antes
  quedaban huérfanos y simplemente dejaban de mostrarse; el resultado visible es el mismo).

### 6. Sin demo

- Se eliminan de la app `DEMO_USUARIO_ID`, `USUARIO_DEMO`, las cuentas demo, la plantilla de
  movimientos por mes y el presupuesto de ejemplo. Los servicios no siembran nada salvo las 7
  categorías predeterminadas del sistema.
- La plantilla de datos pasa a los tests (*mi decisión*). Un módulo de apoyo en `tests/` crea un
  usuario de prueba con las mismas cuentas y siembra los mismos movimientos y presupuestos que antes,
  de modo que los tests existentes comprueben las mismas cifras. Los clientes de prueba inician
  sesión con ese usuario.
- `app/web/preview.py` (la vista previa decorativa del login) se queda: son números de adorno, no
  datos de ningún usuario.

### 7. Límite de intentos y otras defensas

- **Límite de intentos** (en memoria del proceso, como el límite de la IA; *mi decisión*):
  - Login: 5 fallos por correo y por IP en 15 minutos. El siguiente intento da 429 hasta que pase la
    ventana, y un login correcto limpia el contador de ese correo.
  - Registro: 5 intentos por IP por hora.
- **Origen:** las peticiones `POST`/`PUT`/`DELETE` a `/api/` que traen la cabecera `Origin` y no
  coinciden con el host se rechazan con 403. Es una defensa extra contra CSRF, además de `SameSite`.
- **Cabeceras de seguridad** en todas las respuestas: `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`. Sin CSP por ahora, porque la app usa un
  script en línea a propósito (auditoría de rendimiento A10).

### 8. Tests

- **Registro:** 201 y sesión abierta; correo repetido con otras mayúsculas da 422; nombre vacío,
  correo malo y contraseña de 7 o de 129 caracteres dan 422 con el campo correcto.
- **Contraseñas:** el hash guardado empieza por `$argon2id$`; un hash SHA-256 viejo deja entrar y
  queda convertido a Argon2.
- **Sesión:** la sesión vence según «Recordarme»; logout la cierra; la sesión se renueva al entrar.
- **Protección:** sin sesión cada página da 303 a `/login` y cada endpoint 401; con sesión, `/login` y
  `/registro` llevan a `/resumen`.
- **Aislamiento** entre dos usuarios (sección 5).
- **Límite de intentos:** 429 al pasarse y vuelve a funcionar al terminar la ventana (con el reloj
  simulado).
- **Origen y cabeceras.**
- **Usuario nuevo sin datos:** todas las páginas responden 200.
- **Pantallas:** `/registro` trae el formulario y el enlace a `/login`; el login ya no enlaza a
  `/recuperar-contrasena`.

## Restricciones

- Se trabaja en una rama nueva desde `develop`, porque ahí está el backend de usuarios.
- Mismo sistema de diseño del login (`docs/design-system.md`, `login.css`).
- Dependencia nueva: `argon2-cffi` (versión fija en `requirements.txt`).
- Los 439 tests actuales siguen pasando, adaptados solo para iniciar sesión y usar la plantilla desde
  `tests/`.

## Lo que queda al criterio de quien lo construya

Nombres exactos de archivos, clases y funciones; cómo se parte el JS común; el ícono del campo de
nombre (con el mismo trazo de los demás); cómo se ve «Cerrar sesión» en el menú de la barra lateral,
siguiendo el sistema de diseño; y cómo los tests inician sesión (fixture o `dependency_overrides`),
siempre que haya tests que pasen por el login real.
