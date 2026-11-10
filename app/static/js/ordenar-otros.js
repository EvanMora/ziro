/*
 * Ordenar Otros en Categorías (menú "✦ Ordenar Otros ▾"; abrir y cerrar lo maneja desplegable.js).
 * Al abrirlo por primera vez pide GET /api/v1/ia/ordenar-otros y muestra los grupos: a qué
 * categoría pasar cada uno (existente o "Nueva"), con una casilla por movimiento para dejarlo en
 * Otros. "Aceptar" aplica solo los marcados (POST .../aplicar) y el grupo queda como aceptado. Al
 * cerrar el menú, si se aceptó algo, la página se recarga para mostrar los totales nuevos.
 * Todo el texto (descripciones y nombres) se pone con textContent, nunca como HTML.
 */
(() => {
  const raiz = document.querySelector("[data-ordenar-otros]");
  if (!raiz) return;

  const cuerpo = raiz.querySelector("[data-orden-cuerpo]");
  let estado = "nuevo"; // nuevo → cargando → listo | error
  let cambios = false;

  const crear = (etiqueta, clase, texto) => {
    const el = document.createElement(etiqueta);
    if (clase) el.className = clase;
    if (texto != null) el.textContent = texto;
    return el;
  };
  const movimientos = (n) => (n === 1 ? "1 movimiento" : `${n} movimientos`);
  const lista = (descripciones) => descripciones.map((d) => `«${d}»`).join(", ");

  async function pedir(url, opciones = {}) {
    try {
      const respuesta = await fetch(url, {
        credentials: "same-origin",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        ...opciones,
      });
      const datos = await respuesta.json().catch(() => ({}));
      if (respuesta.ok) return { ok: true, datos };
      const errores = datos.errores ?? {};
      const mensaje = errores.nombre ?? errores.movimientos ?? errores.categoria_id ?? errores.general;
      return { ok: false, mensaje: mensaje ?? "El asistente no respondió. Inténtalo de nuevo en un momento." };
    } catch {
      return { ok: false, mensaje: "No se pudo contactar al asistente. Revisa tu conexión." };
    }
  }

  function mostrarCargando() {
    const esqueleto = crear("div", "analisis__esqueleto");
    for (let i = 0; i < 3; i++) esqueleto.append(crear("span"));
    cuerpo.replaceChildren(crear("p", "visually-hidden", "Revisando tus movimientos de Otros…"), esqueleto);
    cuerpo.setAttribute("aria-busy", "true");
  }

  function mostrarError(mensaje) {
    cuerpo.setAttribute("aria-busy", "false");
    const reintentar = crear("button", "btn btn--outline analisis__reintentar", "Reintentar");
    reintentar.type = "button";
    reintentar.addEventListener("click", cargar);
    cuerpo.replaceChildren(crear("p", "field__message field__message--error", mensaje), reintentar);
  }

  // Un grupo: destino, casillas y botón. Devuelve el elemento.
  function grupo(g, indice) {
    const caja = crear("section", "orden__grupo");
    const cabeza = crear("div", "orden__cabeza");
    const destino = crear("p", "orden__destino");
    const nombre = g.categoria ? g.categoria.nombre : g.categoria_nueva;
    destino.append("→ ", crear("strong", null, nombre));
    if (!g.categoria) destino.append(crear("span", "orden__nueva", "Nueva"));
    const conteo = crear("span", "orden__conteo");
    destino.append(" · ", conteo);
    const boton = crear("button", "btn btn--ink orden__aceptar");
    boton.type = "button";
    cabeza.append(destino, boton);

    const ul = crear("ul", "orden__lista");
    const casillas = g.movimientos.map((m, j) => {
      const li = crear("li");
      const etiqueta = crear("label", "orden__item");
      const casilla = crear("input");
      casilla.type = "checkbox";
      casilla.checked = true;
      casilla.value = m.id;
      casilla.id = `orden-${indice}-${j}`;
      etiqueta.append(casilla, crear("span", null, m.descripcion));
      li.append(etiqueta);
      ul.append(li);
      return casilla;
    });
    const error = crear("p", "field__message field__message--error");
    error.hidden = true;

    const marcadas = () => casillas.filter((c) => c.checked);
    function actualizar() {
      const n = marcadas().length;
      conteo.textContent = n === casillas.length ? movimientos(n) : `${n} de ${casillas.length}`;
      boton.textContent = `${g.categoria ? "Aceptar" : "Crear y aceptar"}${n === casillas.length ? "" : ` ${n}`}`;
      boton.disabled = n === 0;
    }
    for (const c of casillas) c.addEventListener("change", actualizar);
    actualizar();

    boton.addEventListener("click", async () => {
      const ids = marcadas().map((c) => Number(c.value));
      if (!ids.length || boton.classList.contains("is-loading")) return;
      boton.classList.add("is-loading");
      boton.disabled = true;
      error.hidden = true;
      const destinoCuerpo = g.categoria ? { categoria_id: g.categoria.id } : { categoria_nueva: g.categoria_nueva };
      const resultado = await pedir("/api/v1/ia/ordenar-otros/aplicar", {
        method: "POST",
        body: JSON.stringify({ movimientos: ids, ...destinoCuerpo }),
      });
      boton.classList.remove("is-loading");
      if (!resultado.ok) {
        error.textContent = resultado.mensaje;
        error.hidden = false;
        actualizar();
        return;
      }
      cambios = true;
      for (const c of casillas) c.disabled = true;
      const hecho = crear("span", "orden__aceptado", `✓ ${movimientos(ids.length)} a ${resultado.datos.categoria.nombre}`);
      boton.replaceWith(hecho);
      caja.classList.add("is-aceptado");
    });

    caja.append(cabeza, ul, error);
    return caja;
  }

  function mostrarOrden(datos, nombreMes) {
    cuerpo.setAttribute("aria-busy", "false");
    const partes = [];
    if (!datos.revisados) {
      partes.push(crear("p", "asistente__texto", `No hay movimientos con descripción en Otros en ${nombreMes}.`));
    } else if (!datos.grupos.length) {
      partes.push(crear("p", "asistente__texto", "No encontré a qué categoría pasarlos: ninguno encaja con claridad."));
    }
    datos.grupos.forEach((g, i) => partes.push(grupo(g, i)));

    const notas = [];
    if (datos.grupos.length && datos.quedan.length) {
      notas.push(`Se quedan en Otros (no encajan en nada): ${lista(datos.quedan.map((m) => m.descripcion))}.`);
    }
    if (datos.sin_descripcion) {
      notas.push(`${movimientos(datos.sin_descripcion)} sin descripción no se ${datos.sin_descripcion === 1 ? "revisó" : "revisaron"}.`);
    }
    if (notas.length) partes.push(crear("p", "orden__resto", notas.join(" ")));
    cuerpo.replaceChildren(...partes);
  }

  async function cargar() {
    const { anio, mes, nombreMes } = raiz.dataset;
    estado = "cargando";
    mostrarCargando();
    const resultado = await pedir(`/api/v1/ia/ordenar-otros?anio=${encodeURIComponent(anio)}&mes=${encodeURIComponent(mes)}`);
    estado = resultado.ok ? "listo" : "error";
    if (resultado.ok) mostrarOrden(resultado.datos, nombreMes);
    else mostrarError(resultado.mensaje);
  }

  // Se pide una sola vez: si se cierra sin aceptar nada y se vuelve a abrir, se ve lo mismo.
  raiz.addEventListener("desplegable:abierto", () => {
    if (estado === "nuevo") cargar();
  });

  // Si se aceptó algo, la página se recarga con los totales nuevos (y el aviso de app-shell.js).
  raiz.addEventListener("desplegable:cerrado", () => {
    if (!cambios) return;
    const url = new URL(location.href);
    url.searchParams.set("aviso", "otros-ordenados");
    location.assign(url);
  });
})();
