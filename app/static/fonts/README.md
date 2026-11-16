# Fuentes

`inter-latin.woff2` e `inter-latin-ext.woff2`: [Inter](https://rsms.me/inter/) de Rasmus Andersson, fuente variable (pesos 400–600), descargada de Google Fonts. Licencia [SIL Open Font License 1.1](https://openfontlicense.org), que permite usarla, incluirla en el proyecto y redistribuirla.

Se sirve desde el propio proyecto (no desde Google) para que cargue sin internet y sin enviar datos de los usuarios a terceros.

## `inter-latin.woff2` recortada (31 KB en vez de 47 KB)

Es la que se descarga en cada página, así que se recortó a lo que usa la app (ver `@font-face` en `css/styles.css`):

- **Mismos caracteres** que el archivo de Google (todo Latin-1, comillas tipográficas, guiones, `…`, `€`, `−`, `‹›`, acentos combinados...): el `unicode-range` del CSS no cambia y ningún carácter pasa a otra fuente.
- **Eje `wght` de 400 a 600** (el original va de 100 a 900): el CSS solo usa 400, 500 y 600.
- **Features que se conservan**: `kern`, `mark`, `mkmk`, `ccmp`, `calt` (signos centrados junto a cifras y mayúsculas, como el `−` de los montos), `locl` y `tnum` (`--numeric: tabular-nums`). Se quitan `frac`, `numr`, `dnom` y `pnum`, que nadie pide.

Para rehacerla, desde el `inter-latin.woff2` original de Google Fonts y con `pip install fonttools brotli`:

```sh
pyftsubset inter-latin-original.woff2 \
  --unicodes="U+0000,U+0020-007E,U+00A0-00AC,U+00AE-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0300-0301,U+0303-0304,U+0308-0309,U+0323,U+2002,U+2009,U+200B,U+2013-2014,U+2018-201A,U+201C-201E,U+2022,U+2026,U+2032-2033,U+2039-203A,U+2044,U+20AC,U+2122,U+2191,U+2193,U+2212,U+FEFF" \
  --layout-features="kern,mark,mkmk,ccmp,calt,locl,tnum" \
  --name-IDs="*" --name-languages="*" --flavor=woff2 --output-file=paso1.woff2
fonttools varLib.instancer paso1.woff2 wght=400:600 -o inter-latin.woff2
```

`inter-latin-ext.woff2` sigue como viene de Google: solo se descarga si una página tiene letras fuera de Latin-1 (ą, ł, ő...).
