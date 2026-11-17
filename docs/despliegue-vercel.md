# Desplegar Ziro en Vercel

Ziro corre en Vercel como una sola función de Python (FastAPI) y guarda los datos en un Postgres de
Neon. En el computador sigue usando SQLite; nada de esto cambia cómo se desarrolla.

**Por qué Postgres:** Vercel no guarda archivos (solo deja escribir en `/tmp`, que se borra) y puede
tener varias copias de la app prendidas a la vez. Con SQLite los datos se perderían.

## Pasos

1. **Crear el proyecto.** En [vercel.com/new](https://vercel.com/new), importar el repo
   `EvanMora/ziro`. Vercel detecta FastAPI solo: la entrada es `app/main.py`. No hay que configurar
   comandos de build ni carpeta de salida. La región (`iad1`) y la versión de Python (3.12) ya están
   en `vercel.json` y `.python-version`.

2. **Conectar la base.** En el proyecto: **Storage → Create Database → Neon** (Marketplace).
   - Región: **aws-us-east-1** (Washington D. C., la misma zona de `iad1`). Cada página hace entre
     10 y 20 consultas: si la base queda en otro continente, la app se siente lenta.
   - Conectarla al proyecto para **Production** y **Preview**. Eso crea sola la variable
     `DATABASE_URL`. Si el asistente pregunta por un prefijo para las variables, dejarlo vacío: la
     app busca exactamente `DATABASE_URL`.

3. **Variables de entorno.** En **Settings → Environment Variables**, para Production y Preview:

   | Variable | Valor |
   |---|---|
   | `SECRET_KEY` | Una clave larga al azar. Generarla con `python -c "import secrets; print(secrets.token_urlsafe(48))"`. **No** usar la del `.env` local. |
   | `GEMINI_API_KEY` | La clave de Gemini (sin ella la app funciona, pero sin las funciones de IA). |
   | `ENVIRONMENT` | `production` (es decir, `ENVIRONMENT=production`). En Vercel la app ya se comporta como producción aunque falte; ponerla lo deja explícito. |

   `DATABASE_URL` ya la puso Neon en el paso 2.

4. **Desplegar.** Con un push a la rama de producción del proyecto (por defecto `main`), o desde la
   terminal con `npx vercel --prod`. La primera petición crea las tablas y las 7 categorías
   predeterminadas.

5. **Verificar en la URL publicada:**
   - [ ] `/` lleva a `/login`.
   - [ ] Crear una cuenta en `/registro` y quedar dentro, en el Resumen.
   - [ ] Crear una cuenta de dinero y registrar un movimiento.
   - [ ] Recargar la página: los datos siguen ahí.
   - [ ] Cerrar sesión y volver a entrar.
   - [ ] En una ventana de incógnito, crear otra cuenta: no ve nada de la primera.
   - [ ] Con `GEMINI_API_KEY`: el asistente de Movimientos responde.

## Problemas comunes

- **La app no arranca y el log dice «DATABASE_URL es obligatoria en producción…»:** falta conectar
  Neon al proyecto (paso 2), o la variable quedó con un prefijo.
- **El log dice «SECRET_KEY es obligatoria en producción…»:** falta la variable o tiene menos de 32
  caracteres (paso 3). Aplica también a las vistas previas.
- **Cada página tarda varios segundos:** revisar que Vercel (`iad1`) y Neon (`aws-us-east-1`) estén
  en la misma región. La primera visita después de un rato sin uso sí tarda un poco más: la función
  y la base se están despertando.
- **«Hiciste demasiados intentos»:** el límite es de 5 intentos fallidos de login por correo o por
  IP cada 15 minutos, y 5 registros por IP por hora. Se guarda en la base (tabla `intentos`).

## Para saber

- **Vistas previas:** cada PR recibe su propia URL, pero todas usan la misma base que producción,
  salvo que en Neon se active una rama de base por vista previa (opcional).
- **Qué se sube:** `.vercelignore` deja por fuera el `.env`, la carpeta `data/` (la base local), los
  tests y la documentación.
- **Cambios en las tablas:** la app crea las tablas que falten, pero no modifica las que ya existen.
  Si un cambio futuro altera una columna, habrá que aplicarlo a mano en Neon (aún no hay migraciones).
- **Datos locales:** la cuenta y los datos del computador (SQLite) no pasan a Vercel; allá se empieza
  con la base vacía.

## Correr los tests contra Postgres

Los tests usan SQLite en memoria. Para repetirlos contra un Postgres real (conviene antes de un
cambio que toque la base):

```bash
docker run -d --name ziro-pg -e POSTGRES_PASSWORD=ziro -e POSTGRES_DB=ziro_test -p 127.0.0.1:55432:5432 postgres:17
ZIRO_TEST_DATABASE_URL=postgresql://postgres:ziro@localhost:55432/ziro_test pytest
docker rm -f ziro-pg
```

Cada test vacía todas las tablas de esa base. Por eso solo se acepta una cuyo nombre contenga `test`
o `prueba`: con la URL de producción, los tests se niegan a correr.
