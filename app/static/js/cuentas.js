/*
 * Sección Cuentas.
 * - "Nueva cuenta" (y los botones "Agregar cuenta/tarjeta") abren el diálogo; tocar una cuenta lo
 *   abre para editarla. Guarda con la API JSON (/api/v1/cuentas), con errores por campo.
 * - Dinero o Tarjeta de crédito: con Dinero se elige la clase; con Tarjeta, cupo y día de pago.
 * - Al editar, "Saldo de hoy" trae el saldo calculado y se puede corregir.
 * - Si la cuenta tiene movimientos, el grupo queda fijo y eliminarla pide a cuál pasarlos.
 * - Después de guardar o eliminar recarga con ?aviso=<clave> (lo muestra app-shell.js) y
 *   ?guardado=<id> resalta la fila.
 * - "Registrar pago" de cada tarjeta lo maneja pago-dialogo.js.
 */
(() => {
  const dialog = document.querySelector("[data-dialogo-cuenta]");
  if (!dialog) return;

  const API = "/api/v1/cuentas";
  const MAX_NOMBRE = 40;
  const ICONO_POR_CLASE = { ahorros: "banco", corriente: "banco", billetera: "celular", efectivo: "billetes", tarjeta: "tarjeta" };
  const reducido = matchMedia("(prefers-reduced-motion: reduce)").matches;

  const form = dialog.querySelector("[data-form-cuenta]");
  const confirmar = dialog.querySelector("[data-confirmar]");
  const titulo = dialog.querySelector("[data-titulo]");
  const alerta = form.querySelector("[data-form-alert]");
  const alertaConfirmar = confirmar.querySelector("[data-confirmar-alert]");
  const guardar = form.querySelector("[data-guardar]");
  const eliminar = form.querySelector("[data-eliminar]");
  const tipoFijo = form.querySelector("[data-tipo-fijo]");
  const notaSaldo = form.querySelector("[data-nota-saldo]");
  const labelSaldo = form.querySelector("[data-label-saldo]");
  const soloDinero = form.querySelectorAll("[data-solo-dinero]");
  const soloTarjeta = form.querySelectorAll("[data-solo-tarjeta]");
  const vistaPrevia = form.querySelector("[data-vista-previa]");
  const mover = confirmar.querySelector("[data-mover]");
  const botonEliminar = confirmar.querySelector("[data-confirmar-eliminar]");
  const textoEliminar = botonEliminar.querySelector("[data-label]");
  const el = form.elements;
  const campos = { nombre: el.nombre, saldo: el.saldo, cupo: el.cupo, dia_pago: el.dia_pago, mover_a: mover.querySelector("select") };
  const idsError = {
    nombre: "cuenta-nombre-error", saldo: "cuenta-saldo-error", cupo: "cuenta-cupo-error", dia_pago: "cuenta-dia-error",
    tipo: "cuenta-tipo-error", icono: "cuenta-icono-error", tono: "cuenta-tono-error", mover_a: "cuenta-mover-error",
  };

  let actual = null; // cuenta en edición (data-cuenta), o null si es nueva
  let ocupado = false;
  let iconoElegido = false; // si la persona tocó el ícono, cambiar la clase ya no lo cambia
  let saldoAbierto = "";    // lo que tenía el campo al abrir: si no cambia, el saldo no se envía

  // ---------- Montos con puntos de miles (como en "Nuevo movimiento") ----------
  const miles = (digitos) => digitos.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const digitosCampo = (texto) => String(texto).replace(/\D/g, "").replace(/^0+(?=\d)/, "");
  const digitosMonto = (monto) => digitosCampo(String(monto).split(".")[0]);

  for (const input of form.querySelectorAll("[data-dinero]")) {
    input.addEventListener("input", () => {
      const digitos = digitosCampo(input.value).slice(0, 12);
      input.value = digitos ? miles(digitos) : "";
    });
  }

  // ---------- Errores ----------
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

  for (const [nombre, input] of Object.entries(campos)) {
    input.addEventListener(input.tagName === "SELECT" ? "change" : "input", () => errorDeCampo(nombre, null));
  }

  // ---------- Grupo, clase, ícono y tono ----------
  const grupo = () => el.grupo.value;
  const tipo = () => (grupo() === "tarjeta" ? "tarjeta" : el.clase.value);

  function mostrarGrupo() {
    const tarjeta = grupo() === "tarjeta";
    for (const nodo of soloDinero) nodo.hidden = tarjeta;
    for (const nodo of soloTarjeta) nodo.hidden = !tarjeta;
    labelSaldo.textContent = tarjeta ? "Deuda de hoy" : "Saldo de hoy";
    notaSaldo.textContent = tarjeta ? "Si no coincide con tu banco, escribe la deuda real." : "Si no coincide con tu banco, escribe el saldo real.";
    errorDeCampo("tipo", null);
  }

  function actualizarVistaPrevia() {
    const tono = el.tono.value;
    vistaPrevia.className = vistaPrevia.className.replace(/\btono-\S+/, `tono-${tono}`);
    for (const nodo of vistaPrevia.querySelectorAll("[data-icono-previa]")) nodo.hidden = nodo.dataset.iconoPrevia !== el.icono.value;
  }

  function iconoPorDefecto() {
    if (iconoElegido) return;
    el.icono.value = ICONO_POR_CLASE[tipo()];
    actualizarVistaPrevia();
  }

  for (const radio of el.grupo) radio.addEventListener("change", () => { mostrarGrupo(); iconoPorDefecto(); });
  el.clase.addEventListener("change", iconoPorDefecto);
  for (const radio of el.icono) radio.addEventListener("change", () => { iconoElegido = true; actualizarVistaPrevia(); });
  for (const radio of el.tono) radio.addEventListener("change", actualizarVistaPrevia);

  // ---------- Abrir y cerrar ----------
  function abrir(cuenta = null, grupoInicial = "dinero") {
    actual = cuenta;
    form.reset();
    limpiarErrores();
    guardar.classList.remove("is-loading", "is-success");
    form.hidden = false;
    confirmar.hidden = true;

    titulo.textContent = cuenta ? "Editar cuenta" : "Nueva cuenta";
    eliminar.hidden = !cuenta;
    const esTarjeta = cuenta ? cuenta.tipo === "tarjeta" : grupoInicial === "tarjeta";
    el.grupo.value = esTarjeta ? "tarjeta" : "dinero";
    if (cuenta && !esTarjeta) el.clase.value = cuenta.tipo;
    const fijo = Boolean(cuenta?.usos);
    for (const radio of el.grupo) radio.disabled = fijo;
    tipoFijo.hidden = !fijo;

    el.nombre.value = cuenta?.nombre ?? "";
    iconoElegido = Boolean(cuenta);
    el.icono.value = cuenta?.icono ?? ICONO_POR_CLASE[esTarjeta ? "tarjeta" : el.clase.value];
    el.tono.value = cuenta?.tono ?? "azul";
    // Un saldo negativo (gastos de más) no cabe en el campo, que es de 0 o más: queda vacío, y si
    // la persona no escribe nada el saldo se conserva.
    const saldo = cuenta && !String(cuenta.saldo).startsWith("-") ? digitosMonto(cuenta.saldo) : "";
    el.saldo.value = saldo ? miles(saldo) : "";
    saldoAbierto = el.saldo.value;
    el.cupo.value = cuenta?.cupo ? miles(digitosMonto(cuenta.cupo)) : "";
    el.dia_pago.value = cuenta?.dia_pago ?? "";
    notaSaldo.hidden = !cuenta;
    mostrarGrupo();
    actualizarVistaPrevia();

    document.querySelector("[data-shell].is-open [data-scrim]")?.click();
    if (!dialog.open) dialog.showModal();
    el.nombre.focus();
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

  for (const boton of document.querySelectorAll("[data-nueva-cuenta]")) {
    boton.addEventListener("click", () => abrir(null, boton.dataset.grupo));
  }
  for (const fila of document.querySelectorAll("[data-editar-cuenta]")) {
    const datos = JSON.parse(fila.dataset.cuenta);
    fila.setAttribute("role", "button");
    fila.setAttribute("tabindex", "0");
    fila.setAttribute("aria-haspopup", "dialog");
    fila.setAttribute("aria-label", `Editar ${datos.nombre}`);
    fila.addEventListener("click", () => abrir(datos));
    fila.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        abrir(datos);
      }
    });
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

  const pedir = (url, opciones) => fetch(url, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    ...opciones,
  });

  // Al editar, el saldo solo se envía si la persona lo cambió (o si cambia de dinero a tarjeta):
  // así un movimiento registrado mientras el diálogo estaba abierto no se pierde al renombrar.
  const enviaSaldo = () => !actual || el.saldo.value !== saldoAbierto || grupo() !== grupoDe(actual);

  function validar() {
    const errores = {};
    const nombre = el.nombre.value.trim().replace(/\s+/g, " ");
    if (!nombre) errores.nombre = "Escribe un nombre.";
    else if (nombre.length > MAX_NOMBRE) errores.nombre = `Máximo ${MAX_NOMBRE} caracteres.`;
    if (enviaSaldo() && !digitosCampo(el.saldo.value)) errores.saldo = grupo() === "tarjeta" ? "Escribe una deuda de 0 o más." : "Escribe un saldo de 0 o más.";
    if (grupo() === "tarjeta") {
      if (!(Number(digitosCampo(el.cupo.value)) > 0)) errores.cupo = "Escribe un cupo mayor que 0.";
      if (!el.dia_pago.value) errores.dia_pago = "Elige un día entre 1 y 31.";
    }
    return errores;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (ocupado) return;
    limpiarErrores();
    const errores = validar();
    if (Object.keys(errores).length) return mostrarErrores(errores, alerta);

    const tarjeta = grupo() === "tarjeta";
    const cuerpo = {
      nombre: el.nombre.value.trim().replace(/\s+/g, " "),
      tipo: tipo(),
      icono: el.icono.value,
      tono: el.tono.value,
      saldo: enviaSaldo() ? digitosCampo(el.saldo.value) : null,
      cupo: tarjeta ? digitosCampo(el.cupo.value) : null,
      dia_pago: tarjeta ? Number(el.dia_pago.value) : null,
    };

    ocupar(guardar, true);
    try {
      const respuesta = await pedir(actual ? `${API}/${actual.id}` : API, {
        method: actual ? "PUT" : "POST",
        body: JSON.stringify(cuerpo),
      });
      const datos = await respuesta.json().catch(() => ({}));
      if (respuesta.ok) {
        guardar.classList.remove("is-loading");
        guardar.classList.add("is-success");
        setTimeout(() => irDespues("cuenta-guardada", datos.id), 450);
        return;
      }
      ocupar(guardar, false);
      if (respuesta.status === 422 && datos.errores) mostrarErrores(datos.errores, alerta);
      else if (respuesta.status === 404) mostrarAlerta(alerta, "Esta cuenta ya no existe. Cierra y recarga la página.");
      else mostrarAlerta(alerta, "No se pudo guardar. Inténtalo de nuevo.");
    } catch {
      ocupar(guardar, false);
      mostrarAlerta(alerta, "No se pudo guardar. Revisa tu conexión e inténtalo de nuevo.");
    }
  });

  // ---------- Eliminar (con confirmación dentro del mismo diálogo) ----------
  const grupoDe = (cuenta) => (cuenta.tipo === "tarjeta" ? "tarjeta" : "dinero");

  // "2 movimientos y 1 pago" (los pagos de tarjeta no son movimientos).
  function textoUsos(movimientos, pagos) {
    const partes = [];
    if (movimientos) partes.push(movimientos === 1 ? "1 movimiento" : `${movimientos} movimientos`);
    if (pagos) partes.push(pagos === 1 ? "1 pago" : `${pagos} pagos`);
    return partes.join(" y ");
  }

  // "Pasar sus movimientos a" solo ofrece las otras cuentas del mismo grupo. Devuelve cuántas hay.
  function prepararMover() {
    let hay = 0;
    for (const opcion of campos.mover_a.options) {
      if (!opcion.value) continue;
      const otra = opcion.dataset.grupo !== grupoDe(actual) || opcion.value === String(actual.id);
      opcion.hidden = otra;
      opcion.disabled = otra;
      if (!otra) hay += 1;
    }
    campos.mover_a.value = "";
    mover.hidden = hay === 0;
    textoEliminar.textContent = hay ? "Pasar y eliminar" : "Eliminar";
    return hay;
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
      const usos = textoUsos(actual.usos - (actual.pagos ?? 0), actual.pagos ?? 0);
      const pronombre = actual.usos === 1 ? "perderlo, elige a qué cuenta pasarlo" : "perderlos, elige a qué cuenta pasarlos";
      if (prepararMover()) {
        texto.replaceChildren(nombre, ` tiene ${usos}. Para no ${pronombre}.`);
      } else {
        const unica = grupoDe(actual) === "tarjeta" ? "tu única tarjeta" : "tu única cuenta de dinero";
        texto.replaceChildren(nombre, ` tiene ${usos} y es ${unica}. Crea otra para pasárselos antes de eliminarla.`);
        botonEliminar.disabled = true;
      }
    } else {
      botonEliminar.disabled = false;
      texto.replaceChildren("¿Eliminar ", nombre, "? No se puede deshacer.");
    }
    if (actual.usos && !mover.hidden) botonEliminar.disabled = false;
    form.hidden = true;
    confirmar.hidden = false;
    (mover.hidden ? confirmar.querySelector("[data-cancelar]") : campos.mover_a).focus();
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
    if (!mover.hidden && !destino) return mostrarErrores({ mover_a: "Elige a qué cuenta pasarlos." }, alertaConfirmar);
    const consulta = destino ? `?${new URLSearchParams({ mover_a: destino })}` : "";
    ocupar(botonEliminar, true);
    try {
      const respuesta = await pedir(`${API}/${actual.id}${consulta}`, { method: "DELETE" });
      if (respuesta.ok || respuesta.status === 404) return irDespues("cuenta-eliminada", null);
      ocupar(botonEliminar, false);
      const datos = await respuesta.json().catch(() => ({}));
      if (respuesta.status === 422 && datos.errores) {
        // La cuenta recibió movimientos después de cargar la página: ahora sí hay que elegir.
        if (datos.errores.mover_a && mover.hidden) prepararMover();
        mostrarErrores(datos.errores, alertaConfirmar);
      } else {
        mostrarAlerta(alertaConfirmar, "No se pudo eliminar. Inténtalo de nuevo.");
      }
    } catch {
      ocupar(botonEliminar, false);
      mostrarAlerta(alertaConfirmar, "No se pudo eliminar. Revisa tu conexión e inténtalo de nuevo.");
    }
  });

  // ---------- ?guardado=<id>: resaltar la cuenta guardada ----------
  const contenedor = document.querySelector("[data-cuentas]");
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
