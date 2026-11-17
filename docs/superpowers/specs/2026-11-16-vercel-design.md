# Preparar Ziro para desplegar en Vercel

## Intención

Juan quiere publicar Ziro en internet, en Vercel, con un link propio. Hoy la app solo corre bien en un
computador con disco, porque guarda todo en SQLite (`data/usuarios.sqlite`). En Vercel la app corre
como funciones que se prenden y se apagan: el disco es de solo lectura, salvo `/tmp`, que se borra.
Además pueden correr varias instancias a la vez y cada una tendría su propia copia de la base. Hay que
dejar la app lista para que, con crear el proyecto en Vercel y conectar una base Postgres, funcione
igual que en local, con la misma seguridad.

## Metas

1. **Base de datos:** en Vercel la app usa Postgres a través de `DATABASE_URL`. En local y en los
   tests sigue con SQLite, sin cambiar nada para quien desarrolla.
2. **Arranque claro:** en producción, sin `DATABASE_URL` o sin `SECRET_KEY`, la app falla al arrancar
   con un mensaje que dice qué falta. Nada de errores raros ni de datos perdidos en silencio.
3. **Seguridad igual que en local:**
   - La cookie lleva `Secure`.
   - El límite de intentos usa la IP real del visitante y es compartido entre instancias, así que vive
     en la base.
   - El límite de consultas a la IA también es compartido.
4. **Configuración de Vercel en el repo:** `vercel.json`, `.vercelignore` y `.python-version`. El
   paquete subido no lleva tests, documentación, la base local ni el `.env`.
5. **Guía de despliegue:** paso a paso para Juan en `docs/despliegue-vercel.md`.
6. **Verificación:** toda la suite pasa con SQLite y, además, contra un Postgres real.

## No metas

- Cloudflare (descartado: sus Workers de Python no garantizan SQLAlchemy ni `argon2-cffi`).
- Migraciones con Alembic: se sigue usando `create_all`, suficiente para el primer despliegue.
- Login con Google, transferencias, README y `docs/alcance.md` (son de Evan).
- Mover la caché del análisis de la IA a la base: puede vivir por instancia, porque solo ahorra
  consultas.
- Dominio propio.

## Antimetas

- Que los tests o el desarrollo local necesiten Postgres.
- Que el despliegue suba el `.env` o `data/usuarios.sqlite`.
- Bajar alguna protección de seguridad para que funcione en Vercel.

## Enfoques considerados

- **Vercel con Postgres (Neon) — elegido.** Juan pidió Vercel. Neon se conecta desde el Marketplace de
  Vercel y crea `DATABASE_URL` sola. SQLAlchemy hace que el cambio sea pequeño.
- **Vercel con SQLite en `/tmp`.** Descartado: los datos se borran y cada instancia tiene los suyos.
- **Un contenedor con disco (Railway, Fly).** Permitiría seguir con SQLite, pero Juan pidió Vercel.

## Decisiones (de Claude, sobre lo que pidió Juan)

**Conexión a la base**
- Orden para elegir la base: `DATABASE_URL`, luego `DATABASE_PATH` y, si no hay ninguna,
  `data/usuarios.sqlite`.
- Las URLs `postgres://` y `postgresql://` pasan a `postgresql+psycopg://`, con el driver
  `psycopg[binary]`.
- Con Postgres, el motor usa `pool_pre_ping=True` y `pool_recycle=300`, porque Neon cierra conexiones
  ociosas.

**Particularidades de Postgres**
- Las 7 categorías predeterminadas se insertan con ids fijos del 1 al 7. En Postgres eso no avanza la
  secuencia, así que después de sembrar hay que ajustarla con `setval`; si no, la primera categoría
  propia choca con el id 1.
- Si dos instancias siembran a la vez, una choca (`IntegrityError`) y se ignora: la otra ya lo hizo.

**Producción e IP**
- Se considera producción si `ENVIRONMENT=production` o si existe la variable `VERCEL`, que Vercel
  pone en todos sus despliegues, incluidas las vistas previas.
- La IP real sale de `x-vercel-forwarded-for`, que Vercel sobrescribe para que nadie la falsifique,
  pero solo si existe `VERCEL`. Fuera de Vercel se usa la IP de la conexión, como hoy.

**Límites compartidos**
- Una tabla `intentos (id, clave, momento)` guarda los intentos de login, de registro y las consultas
  a la IA.
- `reiniciar()` de los tests vacía las tablas a partir de los modelos y ya no usa una lista escrita a
  mano. Así, una tabla nueva de Evan (transferencias) no obliga a tocar `database.py`.

**Configuración de Vercel**
- Python 3.12, la versión por defecto de Vercel. El CI pasa de 3.11 a 3.12 para que coincidan.
- Los estáticos siguen servidos por la app con `StaticFiles`: al haber middleware global, Vercel los
  deja en la función en vez de llevarlos al CDN, así que conservan las cabeceras de seguridad.
- Región `iad1` en Vercel y Neon en `aws-us-east-1`, para que las consultas no crucen continentes.
  Una página hace entre 10 y 20 consultas, así que la distancia se nota mucho.

## Restricciones

- Base: `develop` con los PRs #24 y #25 fusionados. Si aún no lo están, se sale de `feat/metas`, que
  ya los contiene.
- No tocar lo que está haciendo Evan: Google, transferencias, README y `docs/alcance.md`.
- Mensajes y comentarios en español, con el estilo del repo.
