# Preparar Ziro para Vercel: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ziro corre en Vercel con Postgres (Neon) igual que en local con SQLite: mismos datos persistentes, misma seguridad y la misma suite de tests en verde.

**Architecture:**
- **Conexión:** la URL de la base sale de `DATABASE_URL`; en local y en los tests sigue siendo SQLite.
- **Postgres:** se ajustan las secuencias después de insertar con ids fijos, y `reiniciar()` vacía las tablas a partir de los modelos.
- **Configuración común:** un módulo `app/config.py` dice si la app corre en producción. La IP real sale de la cabecera de Vercel.
- **Límites compartidos:** los de login, registro e IA pasan a una tabla `intentos`, para que valgan entre instancias.
- **Despliegue:** `vercel.json`, `.vercelignore` y `.python-version` en la raíz, más una guía paso a paso para Juan.

**Tech Stack:** FastAPI 0.162, SQLAlchemy 2.1, `psycopg[binary]` 3, SQLite (local y tests), Postgres 17 (Neon y Docker para verificar), pytest, Vercel (runtime de Python, Fluid compute).

**Spec:** `docs/superpowers/specs/2026-11-16-vercel-design.md`

## Global Constraints

- **Rama:** `feat/vercel` (ya creada, sale de `feat/metas`). Cuando #24 y #25 estén en `develop`, el PR va hacia `develop`.
- **Archivos de Evan:** no tocar Google OAuth, transferencias, `README.md` ni `docs/alcance.md`.
- **Python 3.12 en Vercel y en el CI:** `.python-version` con `3.12`, y `python-version: '3.12'` en `.github/workflows/ci.yml`.
- **Driver:** `psycopg[binary]==3.3.9`. El esquema de SQLAlchemy es `postgresql+psycopg://`.
- **Producción:** es producción si `ENVIRONMENT == "production"` o si existe la variable de entorno `VERCEL`, con cualquier valor.
- **Mensajes de arranque, exactos:**
  - Base: `"DATABASE_URL es obligatoria en producción: Vercel no guarda archivos, así que SQLite perdería los datos."`
  - Clave: el `RuntimeError` actual de `SECRET_KEY`.
- **IP en Vercel:** la primera IP de `x-vercel-forwarded-for`, sin espacios, y solo si existe `VERCEL`.
- **Límites:** los mismos valores de hoy.
  - Login: 5 por correo y 5 por IP en 15 min.
  - Registro: 5 por IP por hora.
  - IA: `LIMITE_POR_MINUTO = 10` y `LIMITE_POR_DIA = 200`.
- **Región:** Vercel `iad1` y Neon `aws-us-east-1`.
- **Tests:** nunca necesitan Postgres. Con `ZIRO_TEST_DATABASE_URL` toda la suite corre contra esa base.
- **Al terminar cada tarea:** `.venv/bin/python -m pytest -q -p no:cacheprovider` en verde (hoy pasan 696).
- **Estilo:** textos, comentarios y docstrings en español, como en el resto del repo. Commits como `feat(...)` / `fix(...)` / `docs:`, y terminan con `Co-Authored-By` según la configuración del agente.

## Review Focus

1. **URL de Neon con parámetros** (`postgresql://u:p@ep-x-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require`): al normalizarla se conservan usuario, contraseña, host y parámetros, y solo cambia el esquema. Test en la Tarea 1.
2. **Dos instancias en frío siembran a la vez:** el `IntegrityError` de la segunda se ignora y la app arranca. Test en la Tarea 2.
3. **Vista previa de Vercel (`VERCEL` existe y `ENVIRONMENT` no):** sin `SECRET_KEY`, la app tiene que fallar al arrancar. Si generara una clave al azar, cada instancia tendría la suya y cerraría sesiones al azar. Test en la Tarea 1.
4. **`x-vercel-forwarded-for` con varias IPs** (`"190.1.2.3, 10.0.0.1"`) → `190.1.2.3`. Sin la cabecera, aunque esté en Vercel → `request.client.host`. Test en la Tarea 3.
5. **Registro después de un usuario insertado con id fijo** (la plantilla de los tests inserta el id 1): en Postgres el siguiente `INSERT` no puede chocar. Se verifica corriendo toda la suite contra Postgres en la Tarea 2.

---

### Task 1: Configuración de producción y URL de la base

**Files:**
- Create: `app/config.py`
- Modify:
  - `app/services/database.py`: resolver y normalizar la URL; opciones del motor para Postgres.
  - `app/main.py`: `clave_secreta()` y `https_only` usan `es_produccion()`; al importar se llama a `database.url_base_de_datos()` para fallar temprano.
  - `requirements.txt`: agregar `psycopg[binary]==3.3.9` y quitar `pytest`.
  - Create `requirements-dev.txt`: `-r requirements.txt` y `pytest==9.2.0`.
  - `.github/workflows/ci.yml`: Python `3.12`, instalar `requirements-dev.txt` y correr `pytest` con `env: DATABASE_PATH: "sqlite:///:memory:"`.
  - `tests/conftest.py`: quitar `DATABASE_URL` del entorno antes de importar la app (`os.environ.pop("DATABASE_URL", None)`), salvo que exista `ZIRO_TEST_DATABASE_URL` (Tarea 2).
- Test: `tests/test_config_despliegue.py` (nuevo).

**Interfaces:**
- Produces:
  - `app/config.py`:
    - `es_produccion() -> bool`. Lee `os.environ` en cada llamada, no al importar.
    - `en_vercel() -> bool`: `"VERCEL" in os.environ`.
  - `app/services/database.py`:
    - `normalizar_url(url: str) -> str`: si empieza por `postgres://` o `postgresql://` (sin `+driver`), la devuelve con `postgresql+psycopg://`; si no, la devuelve igual.
    - `url_base_de_datos() -> str`:
      - Si hay `os.environ["DATABASE_URL"]` (no vacía), devuelve `normalizar_url` de ese valor.
      - Si no y `es_produccion()`, lanza `RuntimeError` con el mensaje de Global Constraints.
      - Si no, aplica la lógica actual con `DATABASE_PATH` (atributo del módulo, que los tests cambian con monkeypatch): ruta → `sqlite:///ruta`; URL → la misma.
    - `es_postgres(url: str) -> bool`.
  - `obtener_motor_y_sesion(ruta=None)` usa `url_base_de_datos()` cuando `ruta is None`. Con Postgres crea el motor con `pool_pre_ping=True, pool_recycle=300` y sin el `connect_args` de SQLite.

- [ ] **Step 1: Write the failing tests** en `tests/test_config_despliegue.py`. Todos con monkeypatch de `os.environ` y sin conectarse a ninguna base:
  - `test_normalizar_url_postgres` (parametrizado):
    - `"postgres://u:p@h/db"` → `"postgresql+psycopg://u:p@h/db"`
    - `"postgresql://u:p@ep-x-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"` → la misma URL con el esquema `postgresql+psycopg://`
    - `"postgresql+psycopg://u@h/db"` → sin cambios
    - `"sqlite:///data/x.sqlite"` → sin cambios
  - `test_database_url_tiene_prioridad`: con `DATABASE_URL=postgres://u:p@h/db` y `database.DATABASE_PATH="data/otra.sqlite"` → `url_base_de_datos() == "postgresql+psycopg://u:p@h/db"`.
  - `test_sin_database_url_usa_database_path`: sin `DATABASE_URL` y con `DATABASE_PATH="data/x.sqlite"` → `"sqlite:///data/x.sqlite"`.
  - `test_produccion_sin_database_url_falla` (parametrizado): `{"ENVIRONMENT": "production"}` y `{"VERCEL": "1"}` → `pytest.raises(RuntimeError, match="DATABASE_URL es obligatoria")`.
  - `test_vista_previa_de_vercel_exige_secret_key`: `VERCEL=1`, sin `ENVIRONMENT` y sin `SECRET_KEY` → `main.clave_secreta()` lanza `RuntimeError`.
  - `test_es_produccion`: falso sin variables; verdadero con `ENVIRONMENT=production` y verdadero con `VERCEL=1`.
  - `test_requirements_de_produccion`: `requirements.txt` contiene `psycopg[binary]==` y no contiene `pytest`; `requirements-dev.txt` contiene `-r requirements.txt` y `pytest==`.

- [ ] **Step 2:** Correr `.venv/bin/python -m pytest tests/test_config_despliegue.py -q`. Expected: FAIL, porque `app.config` no existe.

- [ ] **Step 3:** Implementar. Antes de correr la suite, `.venv/bin/pip install -r requirements-dev.txt`. `test_sesion.py::test_secret_key_*` debe seguir igual. Agregar `test_vista_previa_*` solo si no está cubierto ahí.

- [ ] **Step 4:** Correr la suite completa. Expected: todo en verde.

- [ ] **Step 5: Commit** `feat(despliegue): La base sale de DATABASE_URL y en producción es obligatoria`.

### Task 2: Postgres correcto (secuencias, siembra concurrente, reiniciar genérico) y suite contra Postgres

**Files:**
- Modify:
  - `app/services/database.py`
  - `tests/plantilla.py`: `crear_usuario` llama a `database.ajustar_secuencias` después de insertar con id fijo.
  - `tests/conftest.py`: soporte de `ZIRO_TEST_DATABASE_URL`.
- Test: `tests/test_config_despliegue.py` (ampliar).

**Interfaces:**
- Produces, en `app/services/database.py`:
  - `ajustar_secuencias(db: Session) -> None`. Con SQLite no hace nada. Con Postgres, para cada tabla de `Base.metadata.sorted_tables` con columna `id`, ejecuta:
    `SELECT setval(pg_get_serial_sequence('<tabla>', 'id'), COALESCE((SELECT MAX(id) FROM <tabla>), 0) + 1, false)`
  - `_sembrar_predeterminadas(db)`: después del `add_all` hace `db.flush()`. Si hay `IntegrityError`, hace `db.rollback()` y vuelve sin error, porque otra instancia ya sembró. Si no, llama a `ajustar_secuencias(db)`.
  - `reiniciar()`:
    - Postgres: `TRUNCATE <todas las tablas> RESTART IDENTITY CASCADE`.
    - SQLite: `DELETE` en `reversed(Base.metadata.sorted_tables)` y limpia `sqlite_sequence` por cada tabla.
    - En los dos casos siembra las predeterminadas. Ya no hay una tupla de tablas escrita a mano.
- `tests/conftest.py`:
  - `URL_TESTS = os.environ.get("ZIRO_TEST_DATABASE_URL", "sqlite:///:memory:")`.
  - `os.environ["DATABASE_PATH"] = URL_TESTS` antes de importar la app.
  - El fixture `_base_de_datos_de_usuarios_en_memoria` hace monkeypatch a `URL_TESTS`, no a `":memory:"` fijo.
  - `tests/test_base_de_los_tests.py` debe seguir pasando: aceptar que `DATABASE_PATH` sea `URL_TESTS` y que la URL nunca contenga `usuarios.sqlite`.

- [ ] **Step 1: Write the failing tests.**
  - `test_siembra_tolera_otra_instancia`: llamar a `_sembrar_predeterminadas` sobre una base que ya tiene las 7 categorías, borrando antes la fila del conteo para forzar el `INSERT` (por ejemplo, con monkeypatch para que el `count` devuelva 0) → no lanza error y siguen siendo 7.
  - `test_reiniciar_no_tiene_lista_de_tablas`: el código de `reiniciar` no contiene la palabra `"pagos_tarjeta"` (inspeccionar con `inspect.getsource`), y después de `reiniciar()` cada tabla de `Base.metadata` tiene 0 filas, salvo `categorias`, que tiene 7.
  - `test_ajustar_secuencias_en_sqlite_no_hace_nada`: no lanza error con la base en memoria.

- [ ] **Step 2:** Correr. Expected: FAIL, porque `ajustar_secuencias` no existe y el `IntegrityError` no se atrapa.

- [ ] **Step 3:** Implementar.

- [ ] **Step 4:** Suite completa con SQLite. Expected: en verde.

- [ ] **Step 5: Suite completa contra Postgres real.**
  - Si `docker info` responde:
    1. `docker run -d --name ziro-pg -e POSTGRES_PASSWORD=ziro -e POSTGRES_DB=ziro_test -p 55432:5432 postgres:17`
    2. Esperar a que `pg_isready -h localhost -p 55432` responda.
    3. `ZIRO_TEST_DATABASE_URL=postgresql+psycopg://postgres:ziro@localhost:55432/ziro_test .venv/bin/python -m pytest -q -p no:cacheprovider`
  - Si Docker no está disponible, pedirle a Juan una URL de una rama de pruebas de Neon (**nunca** la de producción) y usarla en `ZIRO_TEST_DATABASE_URL`.
  - Expected: la misma cantidad de tests en verde que con SQLite.
  - Cada fallo que solo aparezca en Postgres (largos de `String`, orden de `NULL`, secuencias) se corrige en el código de la app. Nunca se adapta el test al error. Se anota en el commit.
  - Al terminar: `docker rm -f ziro-pg`.

- [ ] **Step 6: Commit** `feat(despliegue): Postgres listo: secuencias, siembra concurrente y suite verificada contra Postgres 17`.

### Task 3: IP real detrás de Vercel

**Files:**
- Create: `app/web/red.py`
- Modify: `app/api/auth.py`: `_ip(request)` devuelve `f"ip:{ip_cliente(request)}"`.
- Test: `tests/test_red.py` (nuevo).

**Interfaces:**
- Produces: `app/web/red.py` con `ip_cliente(request: Request) -> str`.
  - Si `en_vercel()` y la cabecera `x-vercel-forwarded-for` no está vacía, devuelve su primer elemento separado por coma, con `strip()`.
  - Si no, devuelve `request.client.host` o `"desconocida"`.
  - Fuera de Vercel **no** se lee ninguna cabecera: alguien podría falsificarla para esquivar el límite de intentos.

- [ ] **Step 1: Write the failing tests.** Construir un `starlette.requests.Request` a mano con `scope` (`headers`, `client`):
  - `test_en_vercel_usa_la_cabecera`: con `VERCEL=1` y la cabecera `"190.1.2.3, 10.0.0.1"` → `"190.1.2.3"`.
  - `test_en_vercel_sin_cabecera_usa_la_conexion`.
  - `test_fuera_de_vercel_ignora_la_cabecera`: sin `VERCEL` y con la cabecera → `client.host`.
  - `test_sin_cliente`: `"desconocida"`.
  - `test_limite_por_ip_en_vercel`: `monkeypatch.setenv("VERCEL", "1")` y `monkeypatch.setenv("DATABASE_URL", os.environ["DATABASE_PATH"])`, que es la URL de la base de los tests, porque en modo producción `url_base_de_datos()` exige `DATABASE_URL`. Después, con `TestClient(app)`: cinco logins malos con la cabecera `x-vercel-forwarded-for: 190.1.2.3` y correos distintos → el sexto con esa IP da 429; con la cabecera `190.9.9.9` da 401.

- [ ] **Step 2:** Correr. Expected: FAIL.

- [ ] **Step 3:** Implementar.

- [ ] **Step 4:** Suite completa. Expected: en verde.

- [ ] **Step 5: Commit** `feat(seguridad): El límite de intentos usa la IP real detrás de Vercel`.

### Task 4: Límites compartidos en la base (login, registro e IA)

**Files:**
- Create: `app/models/intentos.py` (`IntentoDB`), registrado en `app/models/__init__.py`.
- Modify:
  - `app/services/limites.py`: misma API, pero guarda en la base.
  - `app/services/ia.py`: `_registrar_consulta` usa la tabla.
  - `tests/test_ia.py:330`: deja de leer `ia._consultas`.
- Test: `tests/test_limites.py` (nuevo).

**Interfaces:**
- `IntentoDB(id: int PK, clave: String(200), momento: DateTime(timezone=True))`, con `Index("ix_intentos_clave_momento", "clave", "momento")`.
- `LimiteIntentos(nombre: str, maximo: int, ventana: timedelta)`. Guarda la clave como `f"{nombre}:{clave}"`. Mantiene los métodos `bloqueado`, `registrar`, `limpiar` y `reiniciar`.
  - `reiniciar()` borra las filas que empiezan por `f"{nombre}:"`.
  - `registrar` borra de paso las filas con más de 1 día de esa misma clave, para que la tabla no crezca sin fin.
- Instancias:
  - `LOGIN = LimiteIntentos("login", 5, timedelta(minutes=15))`
  - `REGISTRO = LimiteIntentos("registro", 5, timedelta(hours=1))`
- Funciones nuevas de `limites` que usa la IA:
  - `momentos(clave: str, desde: datetime) -> list[datetime]`, del más viejo al más nuevo.
  - `anotar(clave: str, momento: datetime) -> None`.
- Reloj:
  - `limites.ahora()` sigue siendo el reloj de login y registro (los tests le hacen monkeypatch).
  - En `ia.py`, `_reloj()` pasa a `time.time()`, es decir, segundos *epoch* de pared y no `monotonic`, porque ahora se guarda en la base. La clave es `f"ia:{usuario_id}"` y el momento es `datetime.fromtimestamp(_reloj(), timezone.utc)`.
  - Mensajes, ventanas y el cálculo de `espera` iguales a los de hoy.
- `ia.consultas_registradas(usuario_id: int) -> int`: cuántas consultas hay en las últimas 24 h. Solo para tests; reemplaza `len(ia._consultas[1])`.
- `ia.reiniciar_limite()` borra las filas `ia:*`.

- [ ] **Step 1: Write the failing tests** en `tests/test_limites.py`:
  - `test_dos_instancias_comparten_el_limite`: dos objetos `LimiteIntentos("login", 5, ...)` distintos. Cinco `registrar` con uno → `bloqueado` es verdadero en el otro.
  - `test_limites_de_distinto_nombre_no_se_mezclan`: `LOGIN` y `REGISTRO` con la misma clave son independientes.
  - `test_registrar_borra_lo_viejo`: con `limites.ahora` adelantado 2 días, después de un `registrar` quedan 0 filas viejas de esa clave.
  - `test_ia_comparte_el_limite_entre_instancias`: llenar el límite por minuto y luego simular un proceso nuevo con `ia._consultas` inexistente → la siguiente consulta da `LimiteExcedido`.

- [ ] **Step 2:** Correr. Expected: FAIL.

- [ ] **Step 3:** Implementar. Los tests de hoy de límites (`test_api_auth.py`, `test_ia.py`) deben pasar sin cambiar sus expectativas; solo cambia la línea 330 de `test_ia.py`.

- [ ] **Step 4:** Suite completa con SQLite y otra vez contra Postgres (como en la Tarea 2, paso 5). Expected: las dos en verde.

- [ ] **Step 5: Commit** `feat(seguridad): Límites de intentos y de la IA compartidos entre instancias (tabla intentos)`.

### Task 5: Archivos de Vercel y guía de despliegue

**Files:**
- Create:
  - `vercel.json`
  - `.vercelignore`
  - `.python-version`
  - `docs/despliegue-vercel.md`
- Modify: `.env.example`: documentar `DATABASE_URL`, y que en Vercel son obligatorias `SECRET_KEY` y `DATABASE_URL`.
- Test: `tests/test_config_despliegue.py` (ampliar).

**Contenido fijado:**
- `vercel.json`:
  ```json
  {
    "$schema": "https://openapi.vercel.sh/vercel.json",
    "regions": ["iad1"],
    "functions": {
      "app/main.py": {
        "maxDuration": 60,
        "excludeFiles": "{tests/**,docs/**,data/**,.superpowers/**,*.log,Dockerfile}"
      }
    }
  }
  ```
- `.vercelignore`, una entrada por línea:
  - `.env`
  - `.env.*`
  - `!.env.example`
  - `data/`
  - `.venv/`
  - `venv/`
  - `__pycache__/`
  - `.pytest_cache/`
  - `tests/`
  - `docs/`
  - `.superpowers/`
  - `*.sqlite`
  - `*.sqlite3`
  - `*.db`
  - `*.log`
- `.python-version`: `3.12`.
- `docs/despliegue-vercel.md` (para Juan, en español, en pasos numerados):
  1. Crear el proyecto en Vercel importando el repo `EvanMora/ziro`. El framework se detecta solo como FastAPI y la entrada es `app/main.py`.
  2. En **Storage → Marketplace → Neon**, crear la base en la región **aws-us-east-1** y conectarla al proyecto. Eso crea `DATABASE_URL`.
  3. En **Settings → Environment Variables**, para Production y Preview:
     - `SECRET_KEY`, generada con `python -c "import secrets; print(secrets.token_urlsafe(48))"`
     - `GEMINI_API_KEY`
     - `ENVIRONMENT=production`
  4. Desplegar con push a la rama de producción o con `npx vercel --prod`.
  5. **Verificar en la URL publicada:**
     - `/` lleva a `/login`
     - crear una cuenta
     - crear una cuenta de dinero y un movimiento
     - recargar la página: los datos siguen ahí
     - cerrar sesión y volver a entrar
     - en otra ventana de incógnito, otra cuenta no ve nada de la primera
  6. **Problemas comunes:**
     - Si al arrancar sale *«DATABASE_URL es obligatoria…»*, falta conectar Neon.
     - Si sale el mensaje de `SECRET_KEY`, falta la variable.
     - Si cada página tarda segundos, revisar que Vercel y Neon estén en la misma región.
  7. **Nota:** las vistas previas de cada PR usan la misma base, salvo que se configure una rama de Neon por vista previa (opcional).

- [ ] **Step 1: Write the failing tests:**
  - `test_vercel_json`: carga el JSON. `regions == ["iad1"]` y la clave `"app/main.py"` existe con `maxDuration == 60`, y su `excludeFiles` contiene `tests/**` y `data/**`.
  - `test_vercelignore_protege_secretos`: `.vercelignore` contiene las líneas `.env`, `data/` y `*.sqlite`.
  - `test_python_version`: `.python-version` dice `3.12`.
  - `test_ci_usa_312_y_requirements_dev`: `ci.yml` contiene `'3.12'` y `requirements-dev.txt`.
  - `test_guia_de_despliegue`: `docs/despliegue-vercel.md` menciona `DATABASE_URL`, `SECRET_KEY`, `iad1` y `aws-us-east-1`.

- [ ] **Step 2:** Correr. Expected: FAIL.

- [ ] **Step 3:** Crear los archivos.

- [ ] **Step 4:** Suite completa. Expected: en verde.

- [ ] **Step 5: Commit** `feat(despliegue): Configuración de Vercel y guía de despliegue`.

### Task 6: Verificación de producción en local

- [ ] **Step 1: Arrancar como en Vercel** contra el Postgres de Docker de la Tarea 2:
  ```
  VERCEL=1 ENVIRONMENT=production SECRET_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(48))") DATABASE_URL=postgres://postgres:ziro@localhost:55432/ziro_demo .venv/bin/fastapi run app/main.py --port 8020
  ```
  La base `ziro_demo` se crea antes con `psql`.

- [ ] **Step 2: Recorrer la app con un navegador headless.** Hay `playwright-core` en el scratchpad de la sesión anterior; si no está, `npm i playwright-core` en una carpeta temporal y se usa `/usr/bin/chromium`. Pasos:
  1. Registrarse.
  2. Crear una cuenta de dinero, un movimiento, una meta y un aporte.
  3. Cerrar sesión y volver a entrar.
  4. Registrar una segunda persona y confirmar que no ve nada de la primera.

  Expected: todo responde 200/201 y no hay errores de JavaScript, salvo el aviso conocido de View Transition.

  Nota: en producción la cookie lleva `Secure`. Chromium trata `http://localhost` como origen seguro y guarda esas cookies igual, así que el recorrido funciona sin HTTPS. Comprobar además con `curl -i -X POST http://localhost:8020/api/v1/auth/login ...` que la cabecera `Set-Cookie` incluya `secure`, `httponly` y `samesite=lax`. Si se prueba con otra máquina o IP que no sea `localhost`, la cookie no se guarda: eso es lo esperado, no un error.

- [ ] **Step 3: Confirmar que no se sube nada privado.** `npx vercel@65.16.0 build` necesita una sesión de Vercel. Si Juan ya vinculó el proyecto (`npx vercel link`), correrlo y revisar que `.vercel/output` no contenga `.env`, `data/` ni `tests/`. Si no lo vinculó, saltar este paso y anotarlo.

- [ ] **Step 4:** Apagar el servidor y hacer `docker rm -f ziro-pg`.

- [ ] **Step 5:** Abrir el PR `feat/vercel` → `develop`, con base en `develop` si #24 y #25 ya están fusionados. En el cuerpo, enlazar `docs/despliegue-vercel.md` y la lista de verificación de su paso 5.
