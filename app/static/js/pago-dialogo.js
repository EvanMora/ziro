/*
 * Diálogo "Registrar pago" / "Editar pago" de una tarjeta de crédito (Cuentas y Movimientos).
 * - Abre con los botones [data-registrar-pago] (data-tarjeta-id) y desde las filas de pago de
 *   Movimientos con window.dialogoPago.abrir({ tarjetaId, pago }).
 * - Las cuentas de dinero (con saldo) y las tarjetas (con deuda) vienen en data-cuentas-dinero y
 *   data-tarjetas del <dialog>. Al editar, el monto del pago se devuelve a los dos saldos para
 *   calcular cuánto se puede pagar.
 * - Debajo del botón muestra cómo quedan la cuenta de origen y la tarjeta.
 * - Guarda con la API JSON y recarga la página con ?aviso=<clave> (lo muestra app-shell.js).
 */
(() => {
  const dialog = document.querySelector("[data-dialogo-pago]");
  if (!dialog) return;

  const dinero = JSON.parse(dialog.dataset.cuentasDinero);
  const tarjetas = JSON.parse(dialog.dataset.tarjetas);
  const form = dialog.querySelector("[data-form-pago]");
  const confirmar = dialog.querySelector("[data-confirmar]");
  const titulo = dialog.querySelector("[data-titulo]");
  const detalle = dialog.querySelector("[data-detalle]");
  const alerta = form.querySelector("[data-form-alert]");
  const alertaConfirmar = confirmar.querySelector("[data-confirmar-alert]");
  const guardar = form.querySelector("[data-guardar]");
  const textoGuardar = guardar.querySelector("[data-label]");
  const eliminar = form.querySelector("[data-eliminar]");
  const botonEliminar = confirmar.querySelector("[data-confirmar-eliminar]");
  const pagarTodo = form.querySelector("[data-pagar-todo]");
  const textoTodo = pagarTodo.querySelector("[data-todo]");
  const despues = form.querySelector("[data-despues]");
  const campos = { monto: form.elements.monto, cuenta_origen_id: form.elements.cuenta_origen_id, fecha: form.elements.fecha };
  const idsError = { monto: "pago-monto-error", cuenta_origen_id: "pago-origen-error", fecha: "pago-fecha-error" };
  const hoy = campos.fecha.max;

  let tarjeta = null; // { id, nombre, deuda, fecha_texto }
  let actual = null;  // pago en edición { id, monto, cuenta_origen_id, fecha }, o null
  let ocupado = false;
  // Monto exacto (con centavos) cuando el campo se llenó con la deuda completa: el campo solo
  // muestra pesos enteros, pero "Pagar todo" tiene que dejar la tarjeta en $0. Se borra al escribir.
  let montoExacto = null;

  // ---------- Montos ----------
  // El campo muestra pesos enteros con puntos de miles (como el resto de diálogos). Las cuentas se
  // hacen con el valor exacto de la API ("840000.50") y se muestran redondeadas, como el servidor.
  const miles = (digitos) => digitos.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const digitosCampo = (texto) => String(texto).replace(/\D/g, "").replace(/^0+(?=\d)/, "");
  const numero = (monto) => Number(monto) || 0;
  const redondo = (valor) => Math.sign(valor) * Math.round(Math.abs(valor));
  const pesos = (valor) => `${redondo(valor) < 0 ? "−" : ""}$${miles(String(Math.abs(redondo(valor))))}`;
  const exacto = (valor) => valor.toFixed(2).replace(/\.00$/, "");
  const montoActual = () => (montoExacto !== null ? numero(montoExacto) : numero(digitosCampo(campos.monto.value)));

  function llenarMonto(valor) {
    montoExacto = valor > 0 ? exacto(valor) : null;
    campos.monto.value = valor > 0 ? miles(String(Math.abs(redondo(valor)))) : "";
  }

  campos.monto.addEventListener("input", () => {
    montoExacto = null;
    const digitos = digitosCampo(campos.monto.value).slice(0, 12);
    campos.monto.value = digitos ? miles(digitos) : "";
    calcularDespues();
  });
  campos.cuenta_origen_id.addEventListener("change", calcularDespues);

  // Al editar, lo que el pago ya restó vuelve a estar disponible.
  const deudaMaxima = () => numero(tarjeta.deuda) + (actual ? numero(actual.monto) : 0);
  function saldoOrigen(id) {
    const cuenta = dinero.find((c) => String(c.id) === String(id));
    if (!cuenta) return null;
    const devuelto = actual && String(actual.cuenta_origen_id) === String(id) ? numero(actual.monto) : 0;
    return { nombre: cuenta.nombre, saldo: numero(cuenta.saldo) + devuelto };
  }

  function calcularDespues() {
    const monto = montoActual();
    const origen = saldoOrigen(campos.cuenta_origen_id.value);
    if (!monto || !origen) {
      despues.textContent = "";
      return;
    }
    const deuda = deudaMaxima() - monto;
    despues.textContent = `Después: ${origen.nombre} ${pesos(origen.saldo - monto)} · ${tarjeta.nombre} ${deuda > 0.004 ? `debe ${pesos(deuda)}` : "queda al día"}`;
  }

  // ---------- Errores ----------
  function errorDeCampo(nombre, mensaje) {
    const p = idsError[nombre] && document.getElementById(idsError[nombre]);
    if (!p) return false;
    p.textContent = mensaje || "";
    p.hidden = !mensaje;
    if (mensaje) campos[nombre].setAttribute("aria-invalid", "true");
    else campos[nombre].removeAttribute("aria-invalid");
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

  // ---------- Abrir y cerrar ----------
  function abrir({ tarjetaId, pago = null }) {
    tarjeta = tarjetas.find((t) => String(t.id) === String(tarjetaId));
    if (!tarjeta) return;
    actual = pago;
    form.reset();
    limpiarErrores();
    guardar.classList.remove("is-loading", "is-success");
    form.hidden = false;
    confirmar.hidden = true;

    titulo.textContent = pago ? "Editar pago" : `Pagar ${tarjeta.nombre}`;
    const max = deudaMaxima();
    detalle.textContent = pago
      ? `${tarjeta.nombre} · Debe ${pesos(numero(tarjeta.deuda))}`
      : `Debes ${pesos(max)}${tarjeta.fecha_texto !== "Al día" ? ` · ${tarjeta.fecha_texto}` : ""}`;
    textoGuardar.textContent = pago ? "Guardar" : "Registrar pago";
    eliminar.hidden = !pago;
    textoTodo.textContent = pesos(max);
    llenarMonto(pago ? numero(pago.monto) : max);
    campos.cuenta_origen_id.value = pago?.cuenta_origen_id ?? "";
    campos.fecha.value = pago?.fecha ?? hoy;
    calcularDespues();

    document.querySelector("[data-shell].is-open [data-scrim]")?.click();
    if (!dialog.open) dialog.showModal();
    (pago ? campos.monto : campos.cuenta_origen_id).focus();
  }

  pagarTodo.addEventListener("click", () => {
    llenarMonto(deudaMaxima());
    errorDeCampo("monto", null);
    calcularDespues();
  });

  function cerrar() {
    if (!ocupado) dialog.close();
  }

  dialog.querySelector("[data-cerrar]").addEventListener("click", cerrar);
  dialog.addEventListener("cancel", (event) => {
    if (ocupado) event.preventDefault();
  });
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

  for (const boton of document.querySelectorAll("[data-registrar-pago]")) {
    boton.addEventListener("click", () => abrir({ tarjetaId: boton.dataset.tarjetaId }));
  }

  // ---------- Guardar ----------
  function irDespues(aviso) {
    const url = new URL(location.href);
    url.searchParams.delete("guardado");
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

  function validar() {
    const errores = {};
    const monto = montoActual();
    const max = deudaMaxima();
    if (!(monto > 0)) errores.monto = "Escribe un monto mayor que 0.";
    else if (monto > max + 0.004) errores.monto = `No puedes pagar más de lo que debes (${pesos(max)}).`;
    const origen = saldoOrigen(campos.cuenta_origen_id.value);
    if (!origen) errores.cuenta_origen_id = "Elige de qué cuenta sale el pago.";
    else if (monto > 0 && monto > origen.saldo + 0.004) errores.cuenta_origen_id = `No te alcanza: ${origen.nombre} tiene ${pesos(origen.saldo)}.`;
    if (!campos.fecha.value) errores.fecha = "Escribe una fecha válida.";
    else if (campos.fecha.value > hoy) errores.fecha = "La fecha no puede ser futura.";
    return errores;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (ocupado) return;
    limpiarErrores();
    const errores = validar();
    if (Object.keys(errores).length) return mostrarErrores(errores, alerta);

    const cuerpo = {
      monto: montoExacto ?? digitosCampo(campos.monto.value),
      cuenta_origen_id: Number(campos.cuenta_origen_id.value),
      fecha: campos.fecha.value,
    };
    ocupar(guardar, true);
    try {
      const respuesta = await pedir(actual ? `/api/v1/pagos/${actual.id}` : `/api/v1/cuentas/${tarjeta.id}/pagos`, {
        method: actual ? "PUT" : "POST",
        body: JSON.stringify(cuerpo),
      });
      const datos = await respuesta.json().catch(() => ({}));
      if (respuesta.ok) {
        guardar.classList.remove("is-loading");
        guardar.classList.add("is-success");
        setTimeout(() => irDespues(actual ? "pago-guardado" : "pago-registrado"), 450);
        return;
      }
      ocupar(guardar, false);
      if (respuesta.status === 422 && datos.errores) mostrarErrores(datos.errores, alerta);
      else if (respuesta.status === 404) mostrarAlerta(alerta, "Este pago o esta tarjeta ya no existe. Cierra y recarga la página.");
      else mostrarAlerta(alerta, "No se pudo guardar. Inténtalo de nuevo.");
    } catch {
      ocupar(guardar, false);
      mostrarAlerta(alerta, "No se pudo guardar. Revisa tu conexión e inténtalo de nuevo.");
    }
  });

  // ---------- Eliminar (solo al editar) ----------
  eliminar.addEventListener("click", () => {
    if (!actual) return;
    const nombre = document.createElement("strong");
    nombre.textContent = tarjeta.nombre;
    confirmar.querySelector("[data-confirmar-texto]").replaceChildren(
      `¿Eliminar el pago de ${pesos(numero(actual.monto))} a `, nombre, "? Vuelve a sumar a su deuda.");
    mostrarAlerta(alertaConfirmar, null);
    form.hidden = true;
    confirmar.hidden = false;
    confirmar.querySelector("[data-cancelar]").focus();
  });

  confirmar.querySelector("[data-cancelar]").addEventListener("click", () => {
    confirmar.hidden = true;
    form.hidden = false;
    eliminar.focus();
  });

  botonEliminar.addEventListener("click", async () => {
    if (!actual || ocupado) return;
    ocupar(botonEliminar, true);
    try {
      const respuesta = await pedir(`/api/v1/pagos/${actual.id}`, { method: "DELETE" });
      if (respuesta.ok || respuesta.status === 404) return irDespues("pago-eliminado");
      ocupar(botonEliminar, false);
      mostrarAlerta(alertaConfirmar, "No se pudo eliminar. Inténtalo de nuevo.");
    } catch {
      ocupar(botonEliminar, false);
      mostrarAlerta(alertaConfirmar, "No se pudo eliminar. Revisa tu conexión e inténtalo de nuevo.");
    }
  });

  window.addEventListener("pageshow", (event) => {
    if (!event.persisted) return;
    ocupado = false;
    for (const boton of [guardar, botonEliminar]) {
      boton.classList.remove("is-loading", "is-success");
      boton.disabled = false;
    }
    if (dialog.open) dialog.close();
  });

  window.dialogoPago = { abrir };
})();
