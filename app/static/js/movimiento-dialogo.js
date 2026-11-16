/*
 * Diálogo "Nuevo movimiento" / "Editar movimiento" (está en todas las secciones).
 * - Abre con el botón de la barra lateral (o cualquier [data-nuevo-movimiento]) y desde las filas
 *   de Movimientos con window.dialogoMovimiento.abrir(movimiento).
 * - Guarda con la API JSON (/api/v1/movimientos) y muestra los errores por campo, como el login.
 * - Después de guardar o eliminar recarga la sección con ?aviso=<clave> en la URL; el aviso lo
 *   muestra app-shell.js en la página siguiente.
 * - Si hay asistente (GEMINI_API_KEY), al crear se puede escribir una frase y "Completar" llena el
 *   formulario con la sugerencia de /api/v1/ia/interpretar-movimiento. El usuario revisa y guarda.
 *   El asistente de la barra superior (asistente.js) usa interpretar() y abrirConSugerencia().
 * - Se inicializa perezosamente: al cargar solo se registra un clic delegado y la API pública. El
 *   resto (consultas al DOM, listeners) corre la primera vez que hace falta, o antes, en un rato
 *   inactivo, donde además se precalienta el estilo del diálogo para que la primera apertura no
 *   tenga que construirlo todo de golpe.
 */
(() => {
  const dialog = document.querySelector("[data-dialogo-movimiento]");
  if (!dialog) return;

  let api = null;
  const get = () => (api ??= iniciar());

  // Botón de la barra lateral y cualquier otro [data-nuevo-movimiento] (también los que aparezcan
  // después): un solo listener en el documento en vez de uno por enlace.
  document.addEventListener("click", (event) => {
    if (!event.target.closest?.("[data-nuevo-movimiento]")) return;
    event.preventDefault();
    get().abrir(null);
  });

  window.dialogoMovimiento = {
    abrir: (movimiento) => get().abrir(movimiento),
    interpretar: (texto) => get().interpretar(texto),
    abrirConSugerencia: (texto, sugerencia) => get().abrirConSugerencia(texto, sugerencia),
  };

  // Precalentado en ratos inactivos, en dos pasos:
  // 1. Inicializar (consultas al DOM y listeners; ~1-2 ms, ~5 ms con CPU ×4).
  // 2. Calcular una vez el estilo y el layout del diálogo, invisible y sin abrirlo (no roba el foco
  //    ni vuelve inerte la página). Así la primera apertura encuentra calientes las cachés de estilo
  //    y las fuentes, y tarda menos. Cuesta ~8 ms (~35-65 ms con CPU ×4) en un solo bloque, así que
  //    solo se hace en un rato inactivo largo (lo vuelve a intentar cada 250 ms durante unos
  //    segundos) y sin timeout: si la página no descansa, se omite.
  const enReposo = window.requestIdleCallback ?? ((fn) => setTimeout(() => fn({ timeRemaining: () => 50 }), 300));
  let intentos = 12;
  function precalentar(reposo) {
    if (dialog.open) return;
    if (reposo.timeRemaining() < 40) {
      if (--intentos > 0) setTimeout(() => enReposo(precalentar), 250);
      return;
    }
    // fixed: no agranda el scroll de la página; visibility: fuera del árbol de accesibilidad.
    dialog.setAttribute("style", "display:block;position:fixed;inset:0 auto auto 0;visibility:hidden;pointer-events:none");
    dialog.getBoundingClientRect();
    dialog.removeAttribute("style");
  }
  enReposo(() => {
    get();
    enReposo(precalentar);
  }, { timeout: 3000 });

  function iniciar() {
    const API = "/api/v1/movimientos";
    const ESPERA_CHECK = 250; // ms para que se vea el check (draw-check: 360 ms, casi lleno a los 250)
    const form = dialog.querySelector("[data-form-movimiento]");
    const confirmar = dialog.querySelector("[data-confirmar]");
    const titulo = dialog.querySelector("[data-titulo]");
    const alerta = dialog.querySelector("[data-form-alert]");
    const alertaConfirmar = dialog.querySelector("[data-confirmar-alert]");
    const guardar = form.querySelector("[data-guardar]");
    const eliminar = form.querySelector("[data-eliminar]");
    const botonEliminar = confirmar.querySelector("[data-confirmar-eliminar]");
    const campos = {
      monto: form.elements.monto,
      categoria_id: form.elements.categoria_id,
      cuenta_id: form.elements.cuenta_id,
      fecha: form.elements.fecha,
      descripcion: form.elements.descripcion,
    };
    const hoy = campos.fecha.max;

    let actual = null; // movimiento en edición, o null si es nuevo
    let ocupado = false;

    // ---------- Formato ----------
    const miles = (digitos) => digitos.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    // Lo escrito en el campo ("184.300"): solo los dígitos.
    const digitosCampo = (texto) => String(texto).replace(/\D/g, "").replace(/^0+(?=\d)/, "");
    // Un monto de la API ("62000" o "62000.50") en pesos enteros, redondeado como en la lista.
    const digitosMonto = (monto) => String(Math.round(Number(monto) || 0));
    const dinero = (monto, tipo) => `${tipo === "ingreso" ? "+" : "−"}$${miles(digitosMonto(monto))}`;
    // El campo solo muestra pesos enteros. Si el movimiento que se edita tiene centavos (posible por
    // la API), se guarda el monto exacto mientras la persona no lo cambie, para no perderlos.
    let montoExacto = null;
    const montoAEnviar = () => montoExacto ?? digitosCampo(campos.monto.value);

    campos.monto.addEventListener("input", () => {
      montoExacto = null;
      const digitos = digitosCampo(campos.monto.value).slice(0, 12);
      campos.monto.value = digitos ? miles(digitos) : "";
    });

    // ---------- Tipo: la categoría solo ofrece las del tipo elegido ----------
    const tipoElegido = () => form.elements.tipo.value;

    function filtrarCategorias() {
      const tipo = tipoElegido();
      for (const opcion of campos.categoria_id.options) {
        if (!opcion.dataset.tipo) continue;
        const otra = opcion.dataset.tipo !== tipo;
        opcion.hidden = otra;
        opcion.disabled = otra;
      }
      if (campos.categoria_id.selectedOptions[0]?.disabled) campos.categoria_id.value = "";
    }

    for (const radio of form.elements.tipo) radio.addEventListener("change", filtrarCategorias);

    // ---------- Errores (mismo comportamiento que el login) ----------
    function errorDeCampo(nombre, mensaje) {
      const input = campos[nombre];
      const p = document.getElementById(`${nombre}-error`);
      if (!input || !p) return false;
      p.textContent = mensaje || "";
      p.hidden = !mensaje;
      if (mensaje) input.setAttribute("aria-invalid", "true");
      else input.removeAttribute("aria-invalid");
      return true;
    }

    function mostrarAlerta(caja, mensaje) {
      caja.textContent = mensaje || "";
      caja.hidden = !mensaje;
    }

    function limpiarErrores() {
      for (const nombre of Object.keys(campos)) errorDeCampo(nombre, null);
      mostrarAlerta(alerta, null);
      mostrarAlerta(alertaConfirmar, null);
    }

    for (const [nombre, input] of Object.entries(campos)) {
      input.addEventListener(input.tagName === "SELECT" ? "change" : "input", () => {
        if (input.hasAttribute("aria-invalid")) errorDeCampo(nombre, null);
      });
    }

    function validar() {
      const errores = {};
      if (!(Number(montoAEnviar()) > 0)) errores.monto = "Escribe un monto mayor que 0.";
      if (!campos.categoria_id.value) errores.categoria_id = "Elige una categoría.";
      if (!campos.cuenta_id.value) errores.cuenta_id = "Elige una cuenta.";
      if (!campos.fecha.value) errores.fecha = "Escribe una fecha válida.";
      else if (campos.fecha.value > hoy) errores.fecha = "La fecha no puede ser futura.";
      return errores;
    }

    function mostrarErrores(errores) {
      let primero = null;
      for (const [nombre, mensaje] of Object.entries(errores)) {
        if (errorDeCampo(nombre, mensaje)) primero ??= campos[nombre];
        else mostrarAlerta(alerta, mensaje);
      }
      primero?.focus();
    }

    // ---------- Abrir y cerrar ----------
    function abrir(movimiento = null) {
      actual = movimiento;
      // Sin form.reset(): abajo se asigna cada campo (y reiniciarIA vacía la frase), así que
      // reiniciar antes el formulario entero era trabajo repetido.
      limpiarErrores();
      guardar.classList.remove("is-loading", "is-success");
      form.hidden = false;
      confirmar.hidden = true;

      titulo.textContent = movimiento ? "Editar movimiento" : "Nuevo movimiento";
      eliminar.hidden = !movimiento;
      form.elements.tipo.value = movimiento?.tipo ?? "gasto";
      filtrarCategorias();
      campos.monto.value = movimiento ? miles(digitosMonto(movimiento.monto)) : "";
      montoExacto = movimiento && String(movimiento.monto).includes(".") ? String(movimiento.monto) : null;
      campos.categoria_id.value = movimiento?.categoria_id ?? "";
      campos.cuenta_id.value = movimiento?.cuenta_id ?? "";
      campos.fecha.value = movimiento?.fecha ?? hoy;
      campos.descripcion.value = movimiento?.descripcion ?? "";
      reiniciarIA(Boolean(movimiento));

      // En el celular, si el cajón de la barra estaba abierto, se cierra.
      document.querySelector("[data-shell].is-open [data-scrim]")?.click();
      if (!dialog.open) dialog.showModal();
      campos.monto.focus();
    }

    function cerrar() {
      if (!ocupado) dialog.close();
    }

    dialog.querySelector("[data-cerrar]").addEventListener("click", cerrar);
    dialog.addEventListener("cancel", (event) => {
      if (ocupado) event.preventDefault();
    });
    // Clic en el fondo oscuro, fuera de la tarjeta. Tienen que caer fuera tanto el pointerdown como
    // el click: así no cierra al tocar el espacio libre del diálogo a pantalla completa (celular) ni
    // al soltar sobre el fondo una selección de texto que empezó en un campo.
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

    // ---------- Asistente con Gemini: frase → formulario ----------
    const ia = form.querySelector("[data-ia]");
    const iaTexto = ia?.querySelector("[data-ia-texto]");
    const iaBoton = ia?.querySelector("[data-ia-completar]");
    const iaMensaje = ia?.querySelector("[data-ia-mensaje]");
    let iaPeticion = 0; // las respuestas de una petición vieja (diálogo cerrado y reabierto) se ignoran

    function mensajeIA(texto, error = false) {
      if (!ia) return;
      iaMensaje.textContent = texto || "";
      iaMensaje.hidden = !texto;
      iaMensaje.classList.toggle("field__message--error", error);
      if (error) iaTexto.setAttribute("aria-invalid", "true");
      else iaTexto.removeAttribute("aria-invalid");
    }

    function ocuparIA(si) {
      iaBoton.classList.toggle("is-loading", si);
      iaBoton.disabled = si;
    }

    function reiniciarIA(editando) {
      if (!ia) return;
      iaPeticion += 1;
      ia.hidden = editando; // solo al crear
      iaTexto.value = "";
      ocuparIA(false);
      mensajeIA(null);
    }

    function aplicarSugerencia(s) {
      form.elements.tipo.value = s.tipo;
      filtrarCategorias();
      if (s.monto != null) {
        campos.monto.value = miles(digitosMonto(s.monto));
        montoExacto = null;
      }
      if (s.categoria_id != null) campos.categoria_id.value = String(s.categoria_id);
      if (s.cuenta_id != null) campos.cuenta_id.value = String(s.cuenta_id);
      if (s.fecha) campos.fecha.value = s.fecha;
      if (s.descripcion) campos.descripcion.value = s.descripcion;
      limpiarErrores();

      const faltan = [
        ["monto", "el monto"],
        ["categoria_id", "la categoría"],
        ["cuenta_id", "la cuenta"],
      ].filter(([nombre]) => !campos[nombre].value);
      if (faltan.length) {
        mensajeIA(`Revisa los datos y completa ${faltan.map(([, texto]) => texto).join(", ")}.`);
        campos[faltan[0][0]].focus();
      } else {
        mensajeIA("Listo. Revisa los datos y guarda.");
        guardar.focus();
      }
    }

    // Frase → { sugerencia } o { error } (mensaje para el usuario). No toca el formulario.
    async function interpretar(texto) {
      try {
        const respuesta = await pedir("/api/v1/ia/interpretar-movimiento", {
          method: "POST",
          body: JSON.stringify({ texto }),
        });
        const datos = await respuesta.json().catch(() => ({}));
        if (respuesta.ok) return { sugerencia: datos };
        const errores = datos.errores ?? {};
        return { error: errores.texto ?? errores.general ?? "El asistente no respondió. Llena el formulario o inténtalo de nuevo." };
      } catch {
        return { error: "No se pudo contactar al asistente. Revisa tu conexión." };
      }
    }

    // Abre "Nuevo movimiento" ya lleno con una sugerencia que se pidió desde otro lado.
    function abrirConSugerencia(texto, sugerencia) {
      abrir(null);
      if (ia) iaTexto.value = texto;
      aplicarSugerencia(sugerencia);
    }

    async function completarConIA() {
      if (!ia || iaBoton.disabled) return;
      const texto = iaTexto.value.trim();
      if (!texto) {
        mensajeIA("Escribe qué gastaste o recibiste.", true);
        iaTexto.focus();
        return;
      }
      const peticion = ++iaPeticion;
      mensajeIA(null);
      ocuparIA(true);
      const { sugerencia, error } = await interpretar(texto);
      if (peticion !== iaPeticion) return;
      ocuparIA(false);
      if (sugerencia) aplicarSugerencia(sugerencia);
      else mensajeIA(error, true);
    }

    if (ia) {
      iaBoton.addEventListener("click", completarConIA);
      // Enter en la frase completa el formulario; no lo envía.
      iaTexto.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.isComposing) {
          event.preventDefault();
          completarConIA();
        }
      });
      iaTexto.addEventListener("input", () => {
        if (iaTexto.hasAttribute("aria-invalid")) mensajeIA(null);
      });
    }

    // ---------- Después de guardar o eliminar ----------
    // "aviso" es la clave del aviso que muestra app-shell.js al cargar la página siguiente.
    function irDespues(aviso, movimiento) {
      const url = new URL(location.href);
      url.searchParams.delete("nuevo");
      url.searchParams.delete("guardado");
      if (url.pathname === "/movimientos" && movimiento) {
        const [anio, mes] = movimiento.fecha.split("-").map(Number);
        const mesActual = url.searchParams.get("anio") ? [Number(url.searchParams.get("anio")), Number(url.searchParams.get("mes"))] : null;
        const hoyPartes = hoy.split("-").map(Number);
        const vista = mesActual ?? [hoyPartes[0], hoyPartes[1]];
        if (vista[0] !== anio || vista[1] !== mes) {
          // Otro mes: se va a ese mes, sin filtros.
          url.search = "";
          url.searchParams.set("anio", anio);
          url.searchParams.set("mes", mes);
        }
        url.searchParams.set("guardado", movimiento.id);
      }
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
      const errores = validar();
      if (Object.keys(errores).length) {
        mostrarErrores(errores);
        return;
      }

      const cuerpo = {
        tipo: tipoElegido(),
        monto: montoAEnviar(),
        categoria_id: Number(campos.categoria_id.value),
        cuenta_id: Number(campos.cuenta_id.value),
        fecha: campos.fecha.value,
        descripcion: campos.descripcion.value.trim(),
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
          // La página siguiente empieza a cargar mientras el check termina de dibujarse.
          setTimeout(() => irDespues("movimiento-guardado", datos), ESPERA_CHECK);
          return;
        }
        ocupar(guardar, false);
        if (respuesta.status === 422 && datos.errores) mostrarErrores(datos.errores);
        else if (respuesta.status === 404) mostrarAlerta(alerta, "Este movimiento ya no existe. Cierra y recarga la página.");
        else mostrarAlerta(alerta, "No se pudo guardar. Inténtalo de nuevo.");
      } catch {
        ocupar(guardar, false);
        mostrarAlerta(alerta, "No se pudo guardar. Revisa tu conexión e inténtalo de nuevo.");
      }
    });

    // ---------- Eliminar (con confirmación dentro del mismo diálogo) ----------
    eliminar.addEventListener("click", () => {
      if (!actual) return;
      const texto = confirmar.querySelector("[data-confirmar-texto]");
      const nombre = document.createElement("strong");
      nombre.textContent = actual.nombre;
      texto.replaceChildren("¿Eliminar ", nombre, ` por ${dinero(actual.monto, actual.tipo)}? No se puede deshacer.`);
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
        const respuesta = await pedir(`${API}/${actual.id}`, { method: "DELETE" });
        if (respuesta.ok || respuesta.status === 404) {
          irDespues("movimiento-eliminado", null);
          return;
        }
        ocupar(botonEliminar, false);
        mostrarAlerta(alertaConfirmar, "No se pudo eliminar. Inténtalo de nuevo.");
      } catch {
        ocupar(botonEliminar, false);
        mostrarAlerta(alertaConfirmar, "No se pudo eliminar. Revisa tu conexión e inténtalo de nuevo.");
      }
    });

    // Al volver con Atrás, el navegador puede restaurar la página tal como quedó (bfcache): con el
    // diálogo abierto, ocupado y con el check de éxito. Se deja cerrado y listo.
    window.addEventListener("pageshow", (event) => {
      if (!event.persisted) return;
      ocupado = false;
      for (const boton of [guardar, botonEliminar]) {
        boton.classList.remove("is-loading", "is-success");
        boton.disabled = false;
      }
      if (dialog.open) dialog.close();
    });

    return { abrir, interpretar, abrirConSugerencia };
  }
})();
