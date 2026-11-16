/*
 * Sección Metas.
 * - "Nueva meta" abre el diálogo; tocar el nombre de una meta lo abre para editarla o eliminarla.
 * - "Aportar" y "Retirar" abren el diálogo del aporte de esa meta.
 * - En "Últimos aportes", la ✕ pide un segundo toque ("¿Borrar?") antes de borrar.
 * - Guarda con la API JSON (/api/v1/metas), con errores por campo. Después recarga con
 *   ?aviso=<clave> (lo muestra app-shell.js) y ?guardado=<id> resalta la meta.
 */
(() => {
  const dialogMeta = document.querySelector("[data-dialogo-meta]");
  const dialogAporte = document.querySelector("[data-dialogo-aporte]");
  if (!dialogMeta || !dialogAporte) return;

  const API = "/api/v1/metas";
  const MAX_NOMBRE = 40;
  const reducido = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- Montos con puntos de miles (como en Cuentas) ----------
  const miles = (digitos) => digitos.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const digitosCampo = (texto) => String(texto).replace(/\D/g, "").replace(/^0+(?=\d)/, "");
  const digitosMonto = (monto) => digitosCampo(String(monto).split(".")[0]);
  for (const input of document.querySelectorAll("[data-dinero]")) {
    input.addEventListener("input", () => {
      const digitos = digitosCampo(input.value).slice(0, 12);
      input.value = digitos ? miles(digitos) : "";
    });
  }

  const pedir = (url, opciones) => fetch(url, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    ...opciones,
  });

  function irDespues(aviso, id) {
    const url = new URL(location.href);
    url.searchParams.delete("guardado");
    if (id) url.searchParams.set("guardado", id);
    url.searchParams.set("aviso", aviso);
    location.assign(url);
  }

  /* Lo que comparten los dos diálogos: errores por campo, aviso, ocupado y cerrar. */
  function preparar(dialog, ids) {
    const form = dialog.querySelector("form");
    const alerta = form.querySelector("[data-form-alert]");
    const estado = { ocupado: false };

    function errorDeCampo(nombre, mensaje) {
      const p = ids[nombre] && document.getElementById(ids[nombre]);
      if (!p) return false;
      p.textContent = mensaje || "";
      p.hidden = !mensaje;
      const input = form.elements[nombre];
      if (input && mensaje) input.setAttribute("aria-invalid", "true");
      else input?.removeAttribute?.("aria-invalid");
      return true;
    }
    function mostrarAlerta(caja, mensaje) {
      caja.textContent = mensaje || "";
      caja.hidden = !mensaje;
    }
    function limpiar() {
      for (const nombre of Object.keys(ids)) errorDeCampo(nombre, null);
      mostrarAlerta(alerta, null);
    }
    function mostrarErrores(errores, caja = alerta) {
      let primero = null;
      for (const [nombre, mensaje] of Object.entries(errores)) {
        if (errorDeCampo(nombre, mensaje)) primero ??= form.elements[nombre];
        else mostrarAlerta(caja, mensaje);
      }
      primero?.focus();
    }
    function ocupar(boton, si) {
      estado.ocupado = si;
      boton.classList.toggle("is-loading", si);
      boton.disabled = si;
    }
    for (const nombre of Object.keys(ids)) {
      form.elements[nombre]?.addEventListener("input", () => errorDeCampo(nombre, null));
    }
    const cerrar = () => { if (!estado.ocupado) dialog.close(); };
    dialog.querySelector("[data-cerrar]").addEventListener("click", cerrar);
    dialog.addEventListener("cancel", (event) => { if (estado.ocupado) event.preventDefault(); });
    // Clic en el fondo oscuro, fuera de la tarjeta (mismo criterio que cuentas.js).
    const fuera = (event) => {
      const r = dialog.getBoundingClientRect();
      return event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom;
    };
    let pulsoFuera = false;
    dialog.addEventListener("pointerdown", (event) => { pulsoFuera = event.target === dialog && fuera(event); });
    dialog.addEventListener("click", (event) => {
      if (pulsoFuera && event.target === dialog && fuera(event)) cerrar();
      pulsoFuera = false;
    });

    // Guarda la respuesta: ok → aviso y recarga (resaltando la meta idDespues); 422 → errores;
    // 404 → ya no existe.
    async function enviar(boton, url, opciones, aviso, idDespues, cajaErrores = alerta) {
      ocupar(boton, true);
      try {
        const respuesta = await pedir(url, opciones);
        const datos = respuesta.status === 204 ? {} : await respuesta.json().catch(() => ({}));
        if (respuesta.ok) {
          boton.classList.remove("is-loading");
          boton.classList.add("is-success");
          setTimeout(() => irDespues(aviso, idDespues(datos)), reducido ? 0 : 450);
          return;
        }
        ocupar(boton, false);
        if (respuesta.status === 422 && datos.errores) mostrarErrores(datos.errores, cajaErrores);
        else if (respuesta.status === 404) mostrarAlerta(cajaErrores, "Esta meta ya no existe. Cierra y recarga la página.");
        else mostrarAlerta(cajaErrores, "No se pudo guardar. Inténtalo de nuevo.");
      } catch {
        ocupar(boton, false);
        mostrarAlerta(cajaErrores, "No se pudo guardar. Revisa tu conexión e inténtalo de nuevo.");
      }
    }

    return { form, alerta, estado, limpiar, mostrarErrores, mostrarAlerta, enviar };
  }

  let metaActual = null; // datos (data-meta) de la meta en edición o a la que se aporta

  // ---------- Diálogo de la meta ----------
  const m = preparar(dialogMeta, { nombre: "meta-nombre-error", objetivo: "meta-objetivo-error", fecha_limite: "meta-fecha-error" });
  const tituloMeta = dialogMeta.querySelector("[data-titulo]");
  const guardarMeta = m.form.querySelector("[data-guardar]");
  const eliminar = m.form.querySelector("[data-eliminar]");
  const confirmar = dialogMeta.querySelector("[data-confirmar]");
  const alertaConfirmar = confirmar.querySelector("[data-confirmar-alert]");
  const botonEliminar = confirmar.querySelector("[data-confirmar-eliminar]");
  const campoFecha = m.form.elements.fecha_limite;
  const minimoFecha = campoFecha.min;

  function abrirMeta(datos = null) {
    metaActual = datos;
    m.form.reset();
    m.limpiar();
    guardarMeta.classList.remove("is-loading", "is-success");
    m.form.hidden = false;
    confirmar.hidden = true;
    tituloMeta.textContent = datos ? "Editar meta" : "Nueva meta";
    eliminar.hidden = !datos;
    m.form.elements.nombre.value = datos?.nombre ?? "";
    m.form.elements.objetivo.value = datos ? miles(digitosMonto(datos.objetivo)) : "";
    campoFecha.value = datos?.fecha_limite ?? "";
    // Una fecha que ya pasó se puede conservar al editar (el servidor solo valida si cambia).
    campoFecha.min = datos?.fecha_limite && datos.fecha_limite < minimoFecha ? datos.fecha_limite : minimoFecha;
    document.querySelector("[data-shell].is-open [data-scrim]")?.click();
    if (!dialogMeta.open) dialogMeta.showModal();
    m.form.elements.nombre.focus();
  }

  m.form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (m.estado.ocupado) return;
    m.limpiar();
    const nombre = m.form.elements.nombre.value.trim().replace(/\s+/g, " ");
    const objetivo = digitosCampo(m.form.elements.objetivo.value);
    const errores = {};
    if (!nombre) errores.nombre = "Escribe un nombre.";
    else if (nombre.length > MAX_NOMBRE) errores.nombre = `Máximo ${MAX_NOMBRE} caracteres.`;
    if (!(Number(objetivo) > 0)) errores.objetivo = "Escribe un objetivo mayor que 0.";
    if (Object.keys(errores).length) return m.mostrarErrores(errores);
    const cuerpo = { nombre, objetivo, fecha_limite: campoFecha.value || null };
    m.enviar(guardarMeta, metaActual ? `${API}/${metaActual.id}` : API,
             { method: metaActual ? "PUT" : "POST", body: JSON.stringify(cuerpo) }, "meta-guardada", (datos) => datos.id);
  });

  eliminar.addEventListener("click", () => {
    if (!metaActual) return;
    const texto = confirmar.querySelector("[data-confirmar-texto]");
    const nombre = document.createElement("strong");
    nombre.textContent = metaActual.nombre;
    const aportes = metaActual.aportes;
    const extra = aportes ? ` También se borra${aportes === 1 ? " su aporte" : `n sus ${aportes} aportes y retiros`}.` : "";
    texto.replaceChildren("¿Eliminar ", nombre, `?${extra} No se puede deshacer.`);
    m.mostrarAlerta(alertaConfirmar, null);
    m.form.hidden = true;
    confirmar.hidden = false;
    confirmar.querySelector("[data-cancelar]").focus();
  });
  confirmar.querySelector("[data-cancelar]").addEventListener("click", () => {
    confirmar.hidden = true;
    m.form.hidden = false;
    eliminar.focus();
  });
  botonEliminar.addEventListener("click", () => {
    if (!metaActual || m.estado.ocupado) return;
    m.enviar(botonEliminar, `${API}/${metaActual.id}`, { method: "DELETE" }, "meta-eliminada", () => null, alertaConfirmar);
  });

  // ---------- Diálogo del aporte ----------
  const a = preparar(dialogAporte, { monto: "aporte-monto-error", fecha: "aporte-fecha-error" });
  const tituloAporte = dialogAporte.querySelector("[data-titulo]");
  const guardarAporte = a.form.querySelector("[data-guardar]");
  const etiquetaAporte = guardarAporte.querySelector("[data-label]");
  const notaAporte = dialogAporte.querySelector("[data-aporte-nota]");
  const fechaAporte = a.form.elements.fecha;
  const hoy = fechaAporte.value;
  const dinero = (monto) => `$${miles(digitosMonto(monto))}`;

  function mostrarTipo() {
    const retiro = a.form.elements.tipo.value === "retiro";
    tituloAporte.textContent = `${retiro ? "Retirar de" : "Aportar a"} ${metaActual.nombre}`;
    etiquetaAporte.textContent = retiro ? "Retirar" : "Aportar";
    notaAporte.textContent = retiro
      ? `Tienes ${dinero(metaActual.ahorrado)} ahorrados en esta meta.`
      : "Es plata que apartas para la meta: no cambia el saldo de tus cuentas.";
  }

  function abrirAporte(datos, retiro) {
    metaActual = datos;
    a.form.reset();
    a.limpiar();
    guardarAporte.classList.remove("is-loading", "is-success");
    a.form.elements.tipo.value = retiro ? "retiro" : "aporte";
    for (const radio of a.form.elements.tipo) radio.disabled = Number(datos.ahorrado) <= 0;
    fechaAporte.value = hoy;
    fechaAporte.min = datos.creada_en;
    mostrarTipo();
    if (!dialogAporte.open) dialogAporte.showModal();
    a.form.elements.monto.focus();
  }

  for (const radio of a.form.elements.tipo) radio.addEventListener("change", mostrarTipo);

  a.form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (a.estado.ocupado) return;
    a.limpiar();
    const retiro = a.form.elements.tipo.value === "retiro";
    const monto = digitosCampo(a.form.elements.monto.value);
    const errores = {};
    if (!(Number(monto) > 0)) errores.monto = "Escribe un monto mayor que 0.";
    else if (retiro && Number(monto) > Number(metaActual.ahorrado)) {
      errores.monto = `Solo tienes ${dinero(metaActual.ahorrado)} ahorrados en esta meta.`;
    }
    if (!fechaAporte.value) errores.fecha = "Escribe una fecha válida.";
    if (Object.keys(errores).length) return a.mostrarErrores(errores);
    a.enviar(guardarAporte, `${API}/${metaActual.id}/aportes`,
             { method: "POST", body: JSON.stringify({ monto, fecha: fechaAporte.value, retiro }) },
             retiro ? "retiro-guardado" : "aporte-guardado", () => metaActual.id);
  });

  // ---------- Botones de la página ----------
  for (const boton of document.querySelectorAll("[data-nueva-meta]")) boton.addEventListener("click", () => abrirMeta());

  for (const tarjeta of document.querySelectorAll("[data-meta]")) {
    const datos = JSON.parse(tarjeta.dataset.meta);
    tarjeta.querySelector("[data-editar-meta]").addEventListener("click", () => abrirMeta(datos));
    tarjeta.querySelector("[data-aportar]").addEventListener("click", () => abrirAporte(datos, false));
    tarjeta.querySelector("[data-retirar]").addEventListener("click", () => abrirAporte(datos, true));

    // Borrar un aporte: primer toque arma el botón ("¿Borrar?"), el segundo borra.
    for (const boton of tarjeta.querySelectorAll("[data-borrar-aporte]")) {
      const icono = boton.innerHTML;
      let desarmar = null;
      boton.addEventListener("click", async () => {
        if (!boton.classList.contains("is-armed")) {
          boton.classList.add("is-armed");
          boton.textContent = "¿Borrar?";
          desarmar = setTimeout(() => { boton.classList.remove("is-armed"); boton.innerHTML = icono; }, 3000);
          return;
        }
        clearTimeout(desarmar);
        boton.disabled = true;
        try {
          const respuesta = await pedir(`${API}/${datos.id}/aportes/${boton.dataset.borrarAporte}`, { method: "DELETE" });
          if (respuesta.ok || respuesta.status === 404) return irDespues("aporte-eliminado", datos.id);
          const cuerpo = await respuesta.json().catch(() => ({}));
          boton.textContent = "No se pudo";
          boton.title = cuerpo.errores?.general ?? "No se pudo borrar. Inténtalo de nuevo.";
          boton.setAttribute("aria-label", boton.title);
        } catch {
          boton.textContent = "Sin conexión";
        }
        boton.disabled = false;
        setTimeout(() => { boton.classList.remove("is-armed"); boton.innerHTML = icono; }, 3500);
      });
    }
  }

  // ---------- ?guardado=<id>: resaltar la meta guardada ----------
  const contenedor = document.querySelector("[data-metas]");
  const guardado = contenedor?.dataset.guardado;
  if (guardado) {
    const tarjeta = contenedor.querySelector(`[data-id="${CSS.escape(guardado)}"]`);
    if (tarjeta) {
      tarjeta.classList.add("is-saved");
      tarjeta.scrollIntoView({ block: "center", behavior: reducido ? "auto" : "smooth" });
    }
    const url = new URL(location.href);
    url.searchParams.delete("guardado");
    history.replaceState(null, "", url);
  }

  // Al volver con Atrás desde la bfcache: diálogos cerrados y botones listos.
  window.addEventListener("pageshow", (event) => {
    if (!event.persisted) return;
    m.estado.ocupado = a.estado.ocupado = false;
    for (const boton of [guardarMeta, botonEliminar, guardarAporte]) {
      boton.classList.remove("is-loading", "is-success");
      boton.disabled = false;
    }
    for (const d of [dialogMeta, dialogAporte]) if (d.open) d.close();
  });
})();
