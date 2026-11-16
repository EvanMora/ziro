# Crear cuenta y seguridad de usuarios: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cualquier persona puede crear su cuenta en `/registro`. Cada página y cada endpoint trabajan
solo con los datos del usuario de la sesión. Las contraseñas, la sesión y los intentos de entrada
quedan protegidos. La app no siembra datos de demostración.

**Architecture:**
- **Usuarios** (`app/services/usuarios.py`): hashea con Argon2id y valida en el servidor.
- **Sesión** (`app/web/sesion.py`): la abre y la cierra, y expone la dependencia `usuario_actual`. Un
  manejador en `app/main.py` convierte su excepción en 303 a `/login` o 401 en la API.
- **Límite de intentos** (`app/services/limites.py`): contador en memoria.
- **Datos de prueba:** la plantilla sale de los servicios y pasa a `tests/plantilla.py`, que la
  inyecta envolviendo funciones de los servicios. Así los tests de siempre comprueban las mismas
  cifras.

**Tech Stack:** FastAPI 0.162, Starlette `SessionMiddleware`, SQLAlchemy 2.1 sobre SQLite,
`argon2-cffi`, `email-validator` (ya viene con `fastapi[standard]`), Jinja2, JS sin frameworks y
pytest.

**Spec:** `docs/superpowers/specs/2026-11-16-crear-cuenta-design.md`

## Global Constraints

- Rama `feat/registro-y-seguridad`, desde `develop`.
- Contraseña de 8 a 128 caracteres; nombre de 1 a 100 (sin espacios sobrantes); correo de hasta 254,
  en minúsculas y sin espacios.
- Sesión: «Recordarme» dura 30 días y sin marcar 12 horas. `max_age` de la cookie: 30 días.
  `SameSite=Lax`, y `Secure` si `ENVIRONMENT=production`.
- `SECRET_KEY`: en producción es obligatoria y de al menos 32 caracteres. En desarrollo, si falta, se
  genera una al azar por proceso y se avisa.
- Límite de login: 5 fallos por correo y 5 por IP en 15 minutos → 429. Registro: 5 intentos por IP
  por hora → 429.
- Sin sesión: las páginas responden 303 a `/login`; la API responde 401
  `{"detail": "Inicia sesión para continuar."}`.
- Cabeceras en todas las respuestas: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: same-origin`.
- `POST`, `PUT` y `DELETE` a `/api/` con `Origin` distinto del host → 403.
- Mensajes en español y con el tono del login.
- Los 439 tests actuales siguen pasando con las mismas cifras.
- Al terminar cada tarea: `.venv/bin/python -m pytest -q -p no:cacheprovider` en verde.

## Review Focus

1. **Correo con mayúsculas o espacios al entrar** (`" Ana@X.com "`): debe encontrar la cuenta
   `ana@x.com`. Test en la Tarea 1.
2. **Cookie de sesión vieja sin `expira`** (o con un `usuario_id` que ya no existe): se trata como
   sesión inexistente, sin error 500. Tests en la Tarea 2.
3. **La sesión vence con la página abierta:** los `fetch` de la app reciben 401 y deben llevar a
   `/login` en lugar de mostrar «error». Wrapper de `fetch` en la Tarea 4.
4. **Dos registros simultáneos con el mismo correo:** si la restricción única salta en el INSERT
   (`IntegrityError`), la respuesta es 422 en `email`, no 500. Test en la Tarea 1.
5. **Usuario nuevo sin cuentas ni movimientos:** todas las páginas responden 200. Test en la Tarea 4.

---

### Task 1: Contraseñas con Argon2id y validación del registro y el login

**Files:**
- Modify: `requirements.txt` (agregar `argon2-cffi==25.1.0`)
- Modify: `app/services/usuarios.py`
- Modify: `app/schemas/auth.py` (solo docstrings, si hace falta)
- Test: `tests/test_usuarios_seguridad.py` (nuevo)

**Interfaces:**
- Produces, en `app/services/usuarios.py`:
  - Constantes: `MIN_PASSWORD = 8`, `MAX_PASSWORD = 128`, `MAX_NOMBRE = 100`, `MAX_EMAIL = 254`.
  - `normalizar_email(email: str) -> str`: `strip().lower()`.
  - `crear(email: str, password: str, nombre: str = "") -> Usuario`: lanza
    `ErrorValidacion({campo: mensaje})` con los campos `nombre`, `email` y `password`, todos los
    errores juntos.
  - `verificar(email: str, password: str) -> Usuario | None`.
  - `buscar_por_email(email: str) -> Usuario | None`: compara con `func.lower(UsuarioDB.email)`.

- [ ] **Step 1: Write the failing tests** en `tests/test_usuarios_seguridad.py`:
  - `test_el_hash_es_argon2id`: después de `crear("ana@x.com", "secreta123", "Ana")`, el
    `password_hash` empieza por `"$argon2id$"`.
  - `test_hash_sha256_viejo_entra_y_se_convierte`: insertar un `UsuarioDB` con
    `password_hash=hashlib.sha256(b"secreta123").hexdigest()`. Entonces `verificar(...)` no es None y
    el hash guardado queda empezando por `"$argon2id$"`. Con la contraseña mala devuelve None y el hash
    no cambia.
  - `test_correo_se_normaliza_al_crear_y_al_entrar`: `crear("  Ana@X.COM ", ...)` guarda
    `"ana@x.com"`, y `verificar(" ANA@x.com", "secreta123")` lo encuentra.
  - `test_correo_repetido_sin_importar_mayusculas`: crear `ana@x.com` y luego `ANA@x.com` →
    `ErrorValidacion` con `"email"`.
  - `test_correo_viejo_con_mayusculas_se_encuentra`: insertar directo `email="Ana@X.com"`;
    `buscar_por_email("ana@x.com")` lo encuentra.
  - Parametrizado `test_validaciones_del_registro` (campo esperado en `errores`):
    - `("", "ana@x.com", "secreta123")` → `nombre`
    - `("   ", ...)` → `nombre`
    - `("a"*101, ...)` → `nombre`
    - `("Ana", "no-es-correo", ...)` → `email`
    - `("Ana", "a@b", ...)` → `email`
    - `("Ana", "x"*250+"@x.co", ...)` → `email`
    - `("Ana", "ana@x.com", "1234567")` → `password`
    - `("Ana", "ana@x.com", "x"*129)` → `password`
  - `test_contrasena_de_8_y_de_128_se_aceptan`.
  - `test_carrera_de_registro_da_422`: hacer monkeypatch para que el chequeo previo de duplicado no
    encuentre nada; el segundo `crear` del mismo correo lanza `ErrorValidacion` con `"email"`
    (atrapando `IntegrityError`).
  - `test_login_sin_usuario_igual_verifica_un_hash`: monkeypatch de `usuarios._hasher.verify` que
    cuenta las llamadas; `verificar("nadie@x.com", "x")` lo llama 1 vez.

- [ ] **Step 2:** Ejecutar `.venv/bin/python -m pytest tests/test_usuarios_seguridad.py -q`. Debe
  fallar porque el hash es SHA-256 y no hay validación.

- [ ] **Step 3:** Implementar en `app/services/usuarios.py`:
  - `_hasher = PasswordHasher()`.
  - `_HASH_FALSO = _hasher.hash("contraseña-que-no-existe")`, calculado al importar.
  - La validación del correo usa `email_validator.validate_email(email, check_deliverability=False)`.
  - Mensajes:
    - nombre vacío: «Escribe tu nombre.»
    - nombre largo: «El nombre puede tener hasta 100 caracteres.»
    - correo vacío: «Escribe tu correo electrónico.»
    - correo malo: «Revisa el correo. Debe verse así: nombre@correo.com»
    - correo repetido: «Ese correo ya está registrado.»
    - contraseña corta: «La contraseña debe tener al menos 8 caracteres.»
    - contraseña larga: «La contraseña puede tener hasta 128 caracteres.»
  - En `verificar`:
    - Con hash `$argon2`: `_hasher.verify`. Si pasa y `check_needs_rehash` lo pide, guardar el hash
      nuevo.
    - Sin ese prefijo: comparar SHA-256 con `hmac.compare_digest` y, si coincide, guardar el hash
      Argon2.
    - Sin usuario o sin hash: `_hasher.verify(_HASH_FALSO, password)` dentro de un try, y devolver
      None.
  - Quitar el TODO de SHA-256 del docstring.

- [ ] **Step 4:** Ejecutar `.venv/bin/pip install -r requirements.txt` y luego la suite completa.
  Debe salir todo en verde. `tests/test_api_auth.py` usa contraseñas de 9 o más caracteres, así que
  sigue pasando.

- [ ] **Step 5:** Commit con `feat(auth): Contraseñas con Argon2id y validación del registro en el
  servidor`.

### Task 2: Sesión segura, límite de intentos y API de auth

**Files:**
- Create: `app/services/limites.py`
- Modify: `app/web/sesion.py` (agregar lo de sesión; `USUARIO_DEMO` se queda hasta la Tarea 4)
- Modify: `app/api/auth.py`, `app/main.py`, `.env.example`
- Test: `tests/test_api_auth.py` (ampliar), `tests/test_sesion.py` (nuevo)

**Interfaces:**
- Consumes: `usuarios.crear` y `usuarios.verificar` de la Tarea 1.
- Produces:
  - `app/services/limites.py`:
    - `class LimiteIntentos(maximo: int, ventana: timedelta)`, con `bloqueado(clave: str) -> bool`,
      `registrar(clave: str) -> None`, `limpiar(clave: str) -> None` y `reiniciar() -> None`.
    - Reloj: la función de módulo `ahora() -> datetime` (UTC), para hacerle monkeypatch.
    - Instancias: `LOGIN = LimiteIntentos(5, timedelta(minutes=15))` y
      `REGISTRO = LimiteIntentos(5, timedelta(hours=1))`.
    - `reiniciar_todos() -> None`.
  - `app/web/sesion.py`:
    - `DURACION_RECORDAR = timedelta(days=30)` y `DURACION_NORMAL = timedelta(hours=12)`.
    - `ahora() -> datetime`.
    - `abrir_sesion(request: Request, usuario_id: int, recordar: bool) -> None`: `clear()` y luego
      `usuario_id` + `expira` (timestamp float).
    - `cerrar_sesion(request: Request) -> None`.
    - `class SinSesion(Exception)`.
    - `usuario_opcional(request: Request) -> UsuarioSesion | None`: limpia la sesión si venció, si
      está mal formada o si el usuario no existe.
    - `usuario_actual(request: Request) -> UsuarioSesion`: dependencia de FastAPI; lanza `SinSesion`.
  - `app/main.py`:
    - `clave_secreta() -> str`.
    - Manejador de `SinSesion`: 401 JSON si `request.url.path.startswith("/api/")` y, si no,
      `RedirectResponse("/login", 303)`.
    - `SessionMiddleware(max_age=30 días)`.
  - `RegistroEntrada` no cambia. `LoginEntrada.recordar` ya existe.

- [ ] **Step 1: Write the failing tests.**
  - En `tests/test_sesion.py`:
    - `test_sesion_dura_12_horas_sin_recordar`: entrar sin «Recordarme»; con
      `sesion.ahora` adelantado 12 h + 1 s, `GET /api/v1/categorias` da 401. Se monta en un
      `TestClient` sin el override de la Tarea 4; el endpoint queda protegido en la Tarea 4, así que
      aquí se prueba con una ruta mínima creada en el test que dependa de `usuario_actual`.
    - `test_sesion_dura_30_dias_con_recordar`: a los 29 días responde 200 y a los 30 días + 1 s, 401.
    - `test_cookie_sin_expira_no_es_sesion`: una cookie firmada solo con `{"usuario_id": 1}` da 401.
    - `test_usuario_borrado_pierde_la_sesion`.
    - `test_sesion_se_renueva_al_entrar`: guardar un valor ajeno en la sesión antes de entrar; después
      del login ya no está.
    - `test_secret_key_en_produccion`: con `ENVIRONMENT=production`, `clave_secreta()` lanza
      `RuntimeError` si falta o si mide 31 caracteres, y devuelve la clave si mide 32.
    - `test_secret_key_en_desarrollo`: sin clave devuelve una al azar de al menos 32 caracteres,
      distinta en dos llamadas.
  - En `tests/test_api_auth.py`:
    - `test_registro_valida_en_el_servidor`: nombre vacío → 422 `errores.nombre`; contraseña
      `"1234567"` → 422 `errores.password`.
    - `test_login_bloquea_al_sexto_fallo`: 5 fallos dan 401 y el 6.º da 429, aunque la contraseña
      sea correcta.
    - `test_bloqueo_termina_al_pasar_la_ventana`: con `limites.ahora` adelantado 15 min + 1 s, el
      login correcto da 200.
    - `test_login_correcto_limpia_el_contador_del_correo`.
    - `test_registro_bloquea_al_sexto_intento_por_ip`.
    - `test_logout_cierra_la_sesion`.
  - El `conftest.py` agrega un fixture autouse que llama a `limites.reiniciar_todos()`.

- [ ] **Step 2:** Ejecutar los tests nuevos. Deben fallar.

- [ ] **Step 3: Implementar.**
  - En `auth.py`:
    - La IP sale de `request.client.host` (o `"desconocida"`).
    - Login: si `LOGIN.bloqueado` para `f"correo:{normalizar_email(email)}"` o `f"ip:{ip}"`, responde
      429 con `{"detail": "Hiciste demasiados intentos. Espera unos minutos antes de volver a
      intentar."}`. Un fallo registra las dos claves y un acierto limpia la del correo.
    - Registro: si `REGISTRO.bloqueado(f"ip:{ip}")`, responde 429; si no, registra el intento siempre.
    - Login y registro llaman a `abrir_sesion`; el registro usa `recordar=False`.
    - Logout llama a `cerrar_sesion`.
  - En `main.py`, `clave_secreta()` genera la clave con `secrets.token_urlsafe(48)` y avisa con
    `warnings.warn`.
  - En `.env.example`, documentar que `SECRET_KEY` es obligatoria en producción y cómo generarla
    (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).

- [ ] **Step 4:** Correr la suite completa. Debe salir en verde.

- [ ] **Step 5:** Commit con `feat(auth): Sesión que vence y se renueva, límite de intentos y
  SECRET_KEY obligatoria en producción`.

### Task 3: Sacar el demo de la app y llevar la plantilla a los tests

**Files:**
- Create: `tests/plantilla.py`
- Modify:
  - `app/services/cuentas.py` (quitar `_DEMO`, `_PLANTILLA`, `_sembrar_demo`, `ref_plantilla` y el
    uso de `DEMO_USUARIO_ID`)
  - `app/services/movimientos.py` (quitar `_PLANTILLA` y `_sembrar` con todas sus llamadas)
  - `app/services/presupuestos.py` (quitar `_EJEMPLO` y `_sembrar`)
  - `app/services/comun.py` (quitar `DEMO_USUARIO_ID`)
- Modify: `tests/conftest.py`, `tests/test_cuentas_servicio.py` (el test de `ref_plantilla` pasa a
  usar `tests.plantilla`)

**Interfaces:**
- Produces, en `tests/plantilla.py`:
  - `USUARIO_PRUEBA_ID = 1`.
  - `crear_usuario(id: int, correo: str, nombre: str) -> None`: INSERT directo con hash Argon2 de
    `"secreta123"`.
  - `instalar(monkeypatch) -> None`. Envuelve, solo para `usuario_id == USUARIO_PRUEBA_ID`, estas
    funciones para que siembren antes de llamar a la original:
    - `cuentas.listar` → las 4 cuentas de antes.
    - `movimientos.listar`, `movimientos.desde` y `movimientos._guardar` → los meses, con la misma
      lógica de antes.
    - `presupuestos.del_mes` → el ejemplo del mes anterior.
  - `ref_plantilla(nombre: str) -> CuentaRef | None`.
  - El código de siembra se mueve tal cual, sin cambiar cifras, nombres, ids ni el orden de inserción.
- `conftest.py`: un fixture autouse crea el usuario 1 (Evan Pro, `evanpro@correo.com`) y llama a
  `plantilla.instalar`, salvo en los tests marcados con `@pytest.mark.sin_plantilla`. El marcador se
  registra en `pytest.ini` o en `conftest`. `tests/test_api_auth.py` y `tests/test_sesion.py` llevan
  `pytestmark = pytest.mark.sin_plantilla`.

- [ ] **Step 1:** Escribir `tests/test_sin_demo.py` con `pytestmark = sin_plantilla`:
  - `test_usuario_nuevo_no_tiene_cuentas`: `cuentas.listar(id)` devuelve `[]`.
  - `test_usuario_nuevo_no_tiene_movimientos`: `movimientos.listar(id, 2026, 10).movimientos` es
    `[]`.
  - `test_usuario_nuevo_no_tiene_presupuesto`: `presupuestos.del_mes(id, a, m).creado is False` en
    el mes anterior.
  - `test_categorias_predeterminadas`: `len(categorias.listar(id)) == 7`.
  - `test_la_app_no_habla_de_demo`: `grep` sobre `app/` de `DEMO_USUARIO_ID|_sembrar_demo|ref_plantilla`
    no encuentra nada.

- [ ] **Step 2:** Ejecutarlo. Debe fallar, porque el usuario 1 recibe el demo.

- [ ] **Step 3:** Mover el código y escribir `tests/plantilla.py` y el `conftest`.

- [ ] **Step 4:** Correr la suite completa. Los 439 tests de antes siguen pasando más los nuevos.
  Si una cifra cambia, la plantilla no quedó idéntica: corregir la plantilla, nunca el test.

- [ ] **Step 5:** Commit con `refactor: La app no siembra datos de demostración; la plantilla vive en
  los tests`.

### Task 4: Proteger todas las rutas con el usuario de la sesión

**Files:**
- Modify: `app/web/sesion.py` (quitar `USUARIO_DEMO`)
- Modify: `app/web/views.py`, `app/api/categorias.py`, `app/api/cuentas.py`,
  `app/api/movimientos.py`, `app/api/presupuestos.py` y `app/api/ia.py`
- Modify: `app/main.py`, con la raíz `/`.
- Modify: `app/static/js/app-shell.js`, con el wrapper de `fetch`.
- Modify: `tests/conftest.py`, `tests/test_web_categorias.py` y `tests/test_web_login.py` (en la
  raíz).
- Test: `tests/test_proteccion.py` (nuevo).

**Interfaces:**
- Consumes: `usuario_actual` y `usuario_opcional` de la Tarea 2; `plantilla` de la Tarea 3.
- Cambios:
  - Cada ruta recibe `usuario: UsuarioSesion = Depends(usuario_actual)` y usa `usuario.id`. Las
    funciones `_usuario()` de los routers desaparecen.
  - `_contexto_app` recibe el `UsuarioSesion` y lo pone en `"usuario"`.
  - `GET /` lleva con 303 a `/resumen` si hay sesión y a `/login` si no.
  - `GET /login` lleva con 303 a `/resumen` si hay sesión.
- `conftest.py`: con la plantilla, `app.dependency_overrides[usuario_actual]` devuelve el
  `UsuarioSesion` del usuario 1. Con `sin_plantilla` no hay override.

- [ ] **Step 1:** Escribir `tests/test_proteccion.py` con `pytestmark = sin_plantilla`:
  - Parametrizado sobre `["/resumen", "/movimientos", "/cuentas", "/categorias", "/presupuestos",
    "/presupuestos/nuevo"]`: sin sesión dan 303 con `location == "/login"`.
  - Parametrizado sobre todos los endpoints de la API:
    - `GET /api/v1/categorias`, `POST /api/v1/categorias`, `PUT` y `DELETE /api/v1/categorias/1`
    - `GET` y `POST /api/v1/cuentas`, `PUT` y `DELETE /api/v1/cuentas/1`
    - `POST /api/v1/cuentas/1/pagos`, `PUT` y `DELETE /api/v1/pagos/1`
    - `GET` y `POST /api/v1/movimientos`, `PUT` y `DELETE /api/v1/movimientos/1`
    - `GET` y `PUT /api/v1/presupuestos/2026/10`
    - `POST /api/v1/ia/interpretar-movimiento` y `GET /api/v1/ia/analisis-mes`

    Sin sesión dan 401 con `detail == "Inicia sesión para continuar."`.
  - `test_raiz_sin_sesion_va_al_login` y `test_raiz_con_sesion_va_al_resumen`.
  - `test_login_con_sesion_va_al_resumen`.
  - `test_usuario_nuevo_ve_todas_las_paginas`: registrarse por la API y luego hacer `GET` de cada
    página → 200. La barra lateral muestra su nombre y su correo, y no `Evan Pro`.
  - `test_publicas_sin_sesion`: `/login` 200 y `/static/css/login.css` 200.
  - `test_app_shell_redirige_en_401`: `app/static/js/app-shell.js` contiene `401` y `"/login"`.

- [ ] **Step 2:** Ejecutarlo. Debe fallar.

- [ ] **Step 3: Implementar.**
  - Agregar `Depends(usuario_actual)` en todas las rutas.
  - En `app-shell.js`, envolver `window.fetch`: si la URL es de `/api/` y la respuesta es 401,
    `window.location.assign("/login")`. Se devuelve la respuesta igual.
  - Actualizar `test_la_raiz_lleva_al_resumen` en `test_web_login.py` (ahora con sesión: 303 →
    `/resumen`).
  - `test_web_categorias.py` usa `plantilla.USUARIO_PRUEBA_ID` en lugar de `USUARIO_DEMO`.

- [ ] **Step 4:** Correr la suite completa. Debe salir en verde. Revisar además que
  `grep -rn USUARIO_DEMO app tests` no devuelva nada.

- [ ] **Step 5:** Commit con `feat(auth): Todas las páginas y la API usan el usuario de la sesión`.

### Task 5: Aislamiento entre usuarios y claves foráneas

**Files:**
- Modify: `app/services/database.py` (`PRAGMA foreign_keys=ON` con `event.listens_for(motor,
  "connect")`; docstring sin la frase «aún leen en memoria»)
- Modify: `app/services/categorias.py` (`eliminar` borra los `PresupuestoDB` de esa categoría y de
  ese usuario en la misma transacción, antes de borrar la categoría)
- Test: `tests/test_aislamiento.py` (nuevo, `sin_plantilla`)

**Interfaces:**
- Consumes: `plantilla.crear_usuario`.
- Usa dos clientes, `cliente_a` y `cliente_b`, con login real por `/api/v1/auth/login`.

- [ ] **Step 1: Write the failing tests.**
  - `test_b_no_ve_ni_toca_lo_de_a`. A crea una cuenta, un movimiento, una categoría, una tarjeta con
    un pago y un presupuesto. B no los ve en `GET`, y su `PUT` o `DELETE` sobre cada id da 404 (422
    para el presupuesto, porque no existe la categoría para B). Después, A sigue viendo todo igual.
  - `test_b_no_usa_ids_de_a`: un movimiento de B con la `cuenta_id` de A da 422 `cuenta_id`; con la
    `categoria_id` propia de A da 422 `categoria_id`; un pago de B con la cuenta de origen de A da
    422.
  - `test_claves_foraneas_activas`: `PRAGMA foreign_keys` devuelve 1.
  - `test_eliminar_categoria_con_presupuesto`: una categoría propia con presupuesto se elimina (204)
    y el presupuesto del mes ya no la muestra.

- [ ] **Step 2:** Ejecutarlo. Debe fallar en las claves foráneas y en eliminar una categoría con
  presupuesto. Si falla algún aislamiento, es un hallazgo: corregirlo en el servicio y anotarlo en el
  commit.

- [ ] **Step 3:** Implementar.

- [ ] **Step 4:** Correr la suite completa. Debe salir en verde.

- [ ] **Step 5:** Commit con `feat(seguridad): Claves foráneas activas y tests de aislamiento entre
  usuarios`.

### Task 6: Cabeceras de seguridad y revisión de origen

**Files:**
- Modify: `app/main.py` (un middleware `@app.middleware("http")`)
- Test: `tests/test_cabeceras.py` (nuevo)

- [ ] **Step 1: Write the failing tests.**
  - `test_cabeceras_en_paginas_y_api`: en `/login` y `/api/v1/categorias` están las tres cabeceras
    con sus valores exactos.
  - `test_origen_ajeno_da_403`:
    `POST /api/v1/auth/login` con `headers={"Origin": "https://malo.com"}` → 403.
  - `test_origen_propio_pasa`: con `Origin: http://testserver` → 401 (credenciales), no 403.
  - `test_sin_origin_pasa`.
  - `test_get_con_origen_ajeno_no_se_bloquea`.

- [ ] **Step 2:** Ejecutarlo. Debe fallar.

- [ ] **Step 3:** Implementar. El origen se compara con `f"{request.url.scheme}://{request.headers['host']}"`.
  El 403 lleva `{"detail": "Origen no permitido."}`.

- [ ] **Step 4:** Correr la suite completa. Debe salir en verde.

- [ ] **Step 5:** Commit con `feat(seguridad): Cabeceras de seguridad y rechazo de peticiones de
  otro origen`.

### Task 7: Pantalla de registro

**Files:**
- Create:
  - `app/templates/_acceso.html` (base: encabezado, hero, vista previa y pie, con los bloques
    `nav_accion` y `tarjeta`)
  - `app/templates/registro.html`
  - `app/static/js/acceso-form.js`
  - `app/static/js/registro.js`
- Modify:
  - `app/templates/login.html` (extiende `_acceso.html` y quita «¿Olvidaste tu contraseña?»)
  - `app/static/js/login.js`
  - `app/static/css/login.css` (solo lo mínimo: la pista de la contraseña y la fila de «Recordarme»
    sin enlace)
  - `app/web/views.py` (`GET /registro`; redirige a `/resumen` si hay sesión)
- Test: `tests/test_web_registro.py` (nuevo); revisar `tests/test_web_login.py`,
  `tests/test_login_rendimiento.py` y `tests/test_rendimiento_a*.py` por si comprueban el HTML del
  login.

**Interfaces:**
- `acceso-form.js` expone `window.AccesoForm.crear(form)`, que devuelve:
  - `setFieldError(input, mensaje)`, `showAlert(mensaje)`, `setLoading(cargando, textoCargando,
    textoNormal)`, `setSuccess()`, `goAfterCheck(url)` y `shake()`.
  - Además conecta solo el ojo, Bloq Mayús, borrar el error al escribir y el foco inicial.
- `login.js` y `registro.js` lo usan, cada uno con su `validate()` y su envío.
- `registro.html` incluye:
  - `<form ... action="/api/v1/auth/registro" data-registro-form data-redirect="/resumen" novalidate>`.
  - Los campos `nombre` (`autocomplete="name"`, `maxlength="100"`), `email` y `password`
    (`autocomplete="new-password"`, `minlength="8"`, `maxlength="128"`).
  - La pista `id="password-hint"`: «Mínimo 8 caracteres.».
  - El enlace a `/login` en el encabezado y en el pie de la tarjeta.

- [ ] **Step 1: Write the failing tests** en `tests/test_web_registro.py`:
  - `test_registro_renderiza` (`sin_plantilla`): 200, «Crea tu cuenta»,
    `action="/api/v1/auth/registro"`, `autocomplete="new-password"`, `href="/login"`, la etiqueta
    «Nombre» y «Mínimo 8 caracteres.».
  - `test_registro_con_sesion_va_al_resumen`.
  - `test_login_sin_olvidaste`: `/recuperar-contrasena` y «Olvidaste» no aparecen en `/login`.
  - `test_estaticos_del_registro`: `/static/js/registro.js` y `/static/js/acceso-form.js` dan 200.
  - `test_login_sigue_igual`: los tests de `test_web_login.py` siguen pasando sin cambios (salvo el
    de la raíz de la Tarea 4).
  - `test_flujo_completo`: `POST /api/v1/auth/registro` y luego `GET /resumen` → 200 con el nombre
    de la persona.

- [ ] **Step 2:** Ejecutarlo. Debe fallar.

- [ ] **Step 3: Implementar.**
  - Textos de la tarjeta: «Crea tu cuenta» y «Empieza a ordenar tu dinero en un minuto.».
  - Botón: «Crear cuenta», y mientras carga, «Creando cuenta…».
  - Encabezado: «¿Ya tienes cuenta?» y «Iniciar sesión».
  - Pie: «¿Ya tienes cuenta?» y «Iniciar sesión».
  - Validación del navegador: los mismos mensajes de la Tarea 1.
  - Respuestas:
    - 422: cada `errores[campo]` bajo su input.
    - 429: el mensaje de demasiados intentos.
    - Sin red o un error que no sea 422 ni 429: «No pudimos crear tu cuenta. Intenta de nuevo en unos
      minutos.».
  - El correo se envía con `trim().toLowerCase()` y el nombre con `trim()`.

- [ ] **Step 4:** Correr la suite completa. Debe salir en verde.

- [ ] **Step 5:** Commit con `feat(auth): Pantalla para crear una cuenta`.

### Task 8: Cerrar sesión

**Files:**
- Modify:
  - `app/templates/app/base_app.html` (en `.sb-foot`, un botón «Cerrar sesión» con
    `data-logout`, con ícono y `sb-label` como los demás elementos de la barra)
  - `app/static/js/app-shell.js` (al hacer clic: `POST /api/v1/auth/logout` y luego
    `location.assign("/login")`)
  - El CSS de la barra (`app/static/css/app.css`), con estilos que copian `.sb-toggle`
- Test: `tests/test_proteccion.py` (ampliar)

- [ ] **Step 1:** Escribir los tests:
  - `test_barra_tiene_cerrar_sesion`: `/resumen` contiene `data-logout` y «Cerrar sesión».
  - `test_logout_y_despues_login`: después del logout por la API, `/resumen` da 303 a `/login`.

- [ ] **Step 2:** Ejecutarlo. Debe fallar.

- [ ] **Step 3:** Implementar.

- [ ] **Step 4:** Correr la suite completa. Debe salir en verde.

- [ ] **Step 5:** Commit con `feat(auth): Cerrar sesión desde la barra lateral`.

### Task 9: Verificación en el navegador

- [ ] **Step 1:** Arrancar la app con `.venv/bin/fastapi dev app/main.py --port 8000` y una base
  nueva (`DATABASE_PATH` en el scratchpad).
- [ ] **Step 2:** En Chrome, revisar:
  - `/` lleva al login.
  - El login ya no muestra «¿Olvidaste…?».
  - «Crear cuenta» abre `/registro` y los errores del formulario se ven bien.
  - Crear la cuenta lleva a `/resumen` vacío, con el nombre de la persona en la barra.
  - Registrar una cuenta, un movimiento y un presupuesto funciona.
  - «Cerrar sesión» lleva al login, y `/resumen` vuelve a pedir login.
  - Entrar de nuevo funciona.
  - Una segunda cuenta no ve nada de la primera.
- [ ] **Step 3:** Corregir lo que se vea roto o confuso con datos vacíos (lo mínimo) y hacer commit.
