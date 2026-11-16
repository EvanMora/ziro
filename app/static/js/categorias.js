/*
 * Sección Categorías.
 * - "Nueva categoría" (barra superior) y el lápiz de cada categoría propia abren el diálogo.
 * - Guarda con la API JSON (/api/v1/categorias) y muestra los errores por campo, como Movimientos.
 * - Si la categoría ya tiene movimientos, el tipo queda fijo y eliminarla pide a cuál pasarlos.
 * - Después de guardar o eliminar recarga el mismo mes con ?aviso=<clave> (lo muestra
 *   app-shell.js, que está en todas las secciones) y ?guardado=<id> resalta la fila.
 */
(() => {
  const dialog = document.querySelector("[data-dialogo-categoria]");
  if (!dialog) return;

  const API = "/api/v1/categorias";
  const MAX_NOMBRE = 40;
  const reducido = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const form = dialog.querySelector("[data-form-categoria]");
  const confirmar = dialog.querySelector("[data-confirmar]");
  const titulo = dialog.querySelector("[data-titulo]");
  const alerta = form.querySelector("[data-form-alert]");
  const alertaConfirmar = confirmar.querySelector("[data-confirmar-alert]");
  const guardar = form.querySelector("[data-guardar]");
  const eliminar = form.querySelector("[data-eliminar]");
  const tipoFijo = form.querySelector("[data-tipo-fijo]");
  const mover = confirmar.querySelector("[data-mover]");
  const botonEliminar = confirmar.querySelector("[data-confirmar-eliminar]");
  const textoEliminar = botonEliminar.querySelector("[data-label]");
  const campos = { nombre: form.elements.nombre, mover_a: mover.querySelector("select") };
  const idsError = { nombre: "cat-nombre-error", tipo: "cat-tipo-error", mover_a: "cat-mover-error" };
  const radiosTipo = [...form.elements.tipo];

  let actual = null; // categoría en edición ({ id, nombre, tipo, usos }), o null si es nueva
  let ocupado = false;

  // ---------- Errores (mismo comportamiento que el diálogo de movimientos) ----------
  function errorDeCampo(nombre, mensaje) {
    const p = idsError[nombre] && document.getElementById(idsError[nombre]);
    if (!p) return false;
    p.textContent = mensaje || "";
    p.hidden = !mensaje;
    const input = campos[nombre];
    if (input && mensaje) input.setAttribute("aria-invalid", "true");
    else input?.removeAttribute("aria-invalid");
    return true;
  }

  function mostrarAlerta(caja, mensaje) {
    caja.textContent = mensaje || "";
    caja.hidden = !mensaje;
  }

  function limpiarErrores() {
    for (const nombre of Object.keys(idsError)) errorDeCampo(nombre, null);
    mostrarAlerta(alerta, null);
    mostrarAlerta(alertaConfirmar, null);
  }

  function mostrarErrores(errores, caja) {
    let primero = null;
    for (const [nombre, mensaje] of Object.entries(errores)) {
      if (errorDeCampo(nombre, mensaje)) primero ??= campos[nombre];
      else mostrarAlerta(caja, mensaje);
    }
    primero?.focus();
  }

  campos.nombre.addEventListener("input", () => {
    if (campos.nombre.hasAttribute("aria-invalid")) errorDeCampo("nombre", null);
  });
  campos.mover_a.addEventListener("change", () => errorDeCampo("mover_a", null));
  for (const radio of radiosTipo) radio.addEventListener("change", () => errorDeCampo("tipo", null));

  // ---------- Abrir y cerrar ----------
  function abrir(categoria = null) {
    actual = categoria;
    form.reset();
    limpiarErrores();
    guardar.classList.remove("is-loading", "is-success");
    form.hidden = false;
    confirmar.hidden = true;

    titulo.textContent = categoria ? "Editar categoría" : "Nueva categoría";
    eliminar.hidden = !categoria;
    form.elements.tipo.value = categoria?.tipo ?? "gasto";
    const fijo = Boolean(categoria?.usos);
    for (const radio of radiosTipo) radio.disabled = fijo;
    tipoFijo.hidden = !fijo;
    campos.nombre.value = categoria?.nombre ?? "";

    if (!dialog.open) dialog.showModal();
    campos.nombre.focus();
  }

  function cerrar() {
    if (!ocupado) dialog.close();
  }

  dialog.querySelector("[data-cerrar]").addEventListener("click", cerrar);
  dialog.addEventListener("cancel", (event) => {
    if (ocupado) event.preventDefault();
  });
  // Clic en el fondo oscuro, fuera de la tarjeta (mismo criterio que movimiento-dialogo.js).
  const fueraDeLaTarjeta = (event) => {
    const r = dialog.getBoundingClientRect();
    return event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom;
  };
  let pulsoFuera = false;
  dialog.addEventListener("pointerdown", (event) => {
    pulsoFuera = event.target === dialog && fueraDeLaTarjeta(event);
  });
  dialog.addEventListener("click", (event) => {
    if (pulsoFuera && event.target === dialog && fueraDeLaTarjeta(event)) cerrar();
    pulsoFuera = false;
  });

  for (const boton of document.querySelectorAll("[data-nueva-categoria]")) {
    boton.addEventListener("click", () => abrir(null));
  }
  for (const boton of document.querySelectorAll("[data-editar-categoria]")) {
    boton.addEventListener("click", () => abrir(JSON.parse(boton.dataset.categoria)));
  }

  // ---------- Guardar ----------
  function irDespues(aviso, id) {
    const url = new URL(location.href);
    url.searchParams.delete("guardado");
    if (id) url.searchParams.set("guardado", id);
    url.searchParams.set("aviso", aviso);
    location.assign(url);
  }

  function ocupar(boton, si) {
    ocupado = si;
    boton.classList.toggle("is-loading", si);
    boton.disabled = si;
  }

  async function pedir(url, opciones) {
    return fetch(url, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      ...opciones,
    });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (ocupado) return;
    limpiarErrores();
    const nombre = campos.nombre.value.trim().replace(/\s+/g, " ");
    if (!nombre) return mostrarErrores({ nombre: "Escribe un nombre." }, alerta);
    if (nombre.length > MAX_NOMBRE) return mostrarErrores({ nombre: `Máximo ${MAX_NOMBRE} caracteres.` }, alerta);

    ocupar(guardar, true);
    try {
      const respuesta = await pedir(actual ? `${API}/${actual.id}` : API, {
        method: actual ? "PUT" : "POST",
        body: JSON.stringify({ nombre, tipo: form.elements.tipo.value }),
      });
      const datos = await respuesta.json().catch(() => ({}));
      if (respuesta.ok) {
        guardar.classList.remove("is-loading");
        guardar.classList.add("is-success");
        setTimeout(() => irDespues("categoria-guardada", datos.id), 450);
        return;
      }
      ocupar(guardar, false);
      if ((respuesta.status === 422 || respuesta.status === 403) && datos.errores) mostrarErrores(datos.errores, alerta);
      else if (respuesta.status === 404) mostrarAlerta(alerta, "Esta categoría ya no existe. Cierra y recarga la página.");
      else mostrarAlerta(alerta, "No se pudo guardar. Inténtalo de nuevo.");
    } catch {
      ocupar(guardar, false);
      mostrarAlerta(alerta, "No se pudo guardar. Revisa tu conexión e inténtalo de nuevo.");
    }
  });

  // ---------- Eliminar (con confirmación dentro del mismo diálogo) ----------
  // La lista "Pasar sus movimientos a" solo ofrece las otras categorías del mismo tipo.
  function mostrarMover() {
    for (const opcion of campos.mover_a.options) {
      if (!opcion.value) continue;
      const otra = opcion.dataset.tipo !== actual.tipo || opcion.value === String(actual.id);
      opcion.hidden = otra;
      opcion.disabled = otra;
    }
    campos.mover_a.value = "";
    mover.hidden = false;
    textoEliminar.textContent = "Pasar y eliminar";
  }

  eliminar.addEventListener("click", () => {
    if (!actual) return;
    const texto = confirmar.querySelector("[data-confirmar-texto]");
    const nombre = document.createElement("strong");
    nombre.textContent = actual.nombre;
    limpiarErrores();
    mover.hidden = true;
    textoEliminar.textContent = "Eliminar";
    if (actual.usos) {
      const plural = actual.usos === 1 ? "1 movimiento" : `${actual.usos} movimientos`;
      texto.replaceChildren(nombre, ` tiene ${plural}. Para no perderlos, elige a qué categoría pasarlos.`);
      mostrarMover();
    } else {
      texto.replaceChildren("¿Eliminar ", nombre, "? No se puede deshacer.");
    }
    form.hidden = true;
    confirmar.hidden = false;
    (actual.usos ? campos.mover_a : confirmar.querySelector("[data-cancelar]")).focus();
  });

  confirmar.querySelector("[data-cancelar]").addEventListener("click", () => {
    confirmar.hidden = true;
    form.hidden = false;
    eliminar.focus();
  });

  botonEliminar.addEventListener("click", async () => {
    if (!actual || ocupado) return;
    limpiarErrores();
    const destino = mover.hidden ? "" : campos.mover_a.value;
    if (!mover.hidden && !destino) {
      mostrarErrores({ mover_a: "Elige a qué categoría pasarlos." }, alertaConfirmar);
      return;
    }
    const consulta = destino ? `?${new URLSearchParams({ mover_a: destino })}` : "";
    ocupar(botonEliminar, true);
    try {
      const respuesta = await pedir(`${API}/${actual.id}${consulta}`, { method: "DELETE" });
      if (respuesta.ok || respuesta.status === 404) {
        irDespues("categoria-eliminada", null);
        return;
      }
      ocupar(botonEliminar, false);
      const datos = await respuesta.json().catch(() => ({}));
      if (respuesta.status === 422 && datos.errores) {
        // La categoría recibió movimientos después de cargar la página: ahora sí hay que elegir.
        if (datos.errores.mover_a && mover.hidden) mostrarMover();
        mostrarErrores(datos.errores, alertaConfirmar);
      } else if (respuesta.status === 403 && datos.errores) {
        mostrarErrores(datos.errores, alertaConfirmar);
      } else {
        mostrarAlerta(alertaConfirmar, "No se pudo eliminar. Inténtalo de nuevo.");
      }
    } catch {
      ocupar(botonEliminar, false);
      mostrarAlerta(alertaConfirmar, "No se pudo eliminar. Revisa tu conexión e inténtalo de nuevo.");
    }
  });

  // ---------- ?guardado=<id>: resaltar la categoría guardada ----------
  const contenedor = document.querySelector("[data-categorias]");
  const guardado = contenedor?.dataset.guardado;
  if (guardado) {
    const fila = contenedor.querySelector(`[data-id="${CSS.escape(guardado)}"]`);
    if (fila) {
      fila.classList.add("is-saved");
      fila.scrollIntoView({ block: "center", behavior: reducido ? "auto" : "smooth" });
    }
    const url = new URL(location.href);
    url.searchParams.delete("guardado");
    history.replaceState(null, "", url);
  }

  // Al volver con Atrás desde la bfcache: diálogo cerrado y botones listos.
  window.addEventListener("pageshow", (event) => {
    if (!event.persisted) return;
    ocupado = false;
    for (const boton of [guardar, botonEliminar]) {
      boton.classList.remove("is-loading", "is-success");
      boton.disabled = false;
    }
    if (dialog.open) dialog.close();
  });
})();
