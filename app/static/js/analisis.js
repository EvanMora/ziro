/*
 * Análisis del mes en el Resumen (menú "✦ Analizar mes ▾"; abrir y cerrar lo maneja desplegable.js).
 * Al abrirlo por primera vez pide GET /api/v1/ia/analisis-mes y muestra las observaciones y el
 * consejo. Todo el texto de la IA se pone con textContent, nunca como HTML.
 * - Precarga: con el ratón quieto un momento sobre el botón, o al enfocarlo, se pide antes del clic
 *   para esperar menos. Una sola petición por mes (cada consulta gasta cupo de IA); al abrir se
 *   reutiliza la que está en curso o su resultado. Si la precarga falló, abrir lo pide como siempre.
 */
(() => {
  const raiz = document.querySelector("[data-analisis]");
  if (!raiz) return;

  const cuerpo = raiz.querySelector("[data-analisis-cuerpo]");
  const boton = raiz.querySelector("[data-desplegable-boton]");
  const RETARDO_PRECARGA = 150; // ms de hover o foco sostenido: una pasada rápida no gasta consulta
  let estado = "nuevo"; // nuevo → cargando → listo | error
  let precarga = null; // { clave, promesa, resultado }: la pedida antes de abrir el menú
  let temporizador = 0;

  const crear = (etiqueta, clase, texto) => {
    const el = document.createElement(etiqueta);
    if (clase) el.className = clase;
    if (texto) el.textContent = texto;
    return el;
  };

  function mostrarCargando() {
    const esqueleto = crear("div", "analisis__esqueleto");
    for (let i = 0; i < 3; i++) esqueleto.append(crear("span"));
    cuerpo.replaceChildren(crear("p", "visually-hidden", "Analizando tus cifras…"), esqueleto);
    cuerpo.setAttribute("aria-busy", "true");
  }

  function mostrarAnalisis(datos, nombreMes) {
    cuerpo.setAttribute("aria-busy", "false");
    if (datos.sin_datos) {
      cuerpo.replaceChildren(crear("p", "asistente__texto", `No hay movimientos en ${nombreMes} para analizar.`));
      return;
    }
    const partes = [];
    if (datos.observaciones.length) {
      const lista = crear("ul", "analisis__lista");
      for (const texto of datos.observaciones) lista.append(crear("li", null, texto));
      partes.push(lista);
    }
    if (datos.consejo) {
      const consejo = crear("p", "analisis__consejo");
      consejo.append(crear("strong", null, "Consejo"), crear("span", null, datos.consejo));
      partes.push(consejo);
    }
    cuerpo.replaceChildren(...partes);
  }

  function mostrarError(mensaje) {
    cuerpo.setAttribute("aria-busy", "false");
    const reintentar = crear("button", "btn btn--outline analisis__reintentar", "Reintentar");
    reintentar.type = "button";
    reintentar.addEventListener("click", () => cargar());
    cuerpo.replaceChildren(crear("p", "field__message field__message--error", mensaje), reintentar);
  }

  // Hace la petición y nunca falla: resuelve { ok: true, datos } o { ok: false, mensaje }.
  async function pedir(anio, mes) {
    try {
      const url = `/api/v1/ia/analisis-mes?anio=${encodeURIComponent(anio)}&mes=${encodeURIComponent(mes)}`;
      const respuesta = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
      const datos = await respuesta.json().catch(() => ({}));
      if (respuesta.ok) return { ok: true, datos };
      return { ok: false, mensaje: datos.errores?.general ?? "El asistente no respondió. Inténtalo de nuevo en un momento." };
    } catch {
      return { ok: false, mensaje: "No se pudo contactar al asistente. Revisa tu conexión." };
    }
  }

  async function cargar({ reutilizar = false } = {}) {
    const { anio, mes, nombreMes } = raiz.dataset;
    // Sirve la precarga del mismo mes si sigue en curso o salió bien; si falló, se pide de nuevo.
    const previa = reutilizar && precarga?.clave === `${anio}-${mes}` && precarga.resultado?.ok !== false
      ? precarga.promesa : null;
    precarga = null;
    estado = "cargando";
    mostrarCargando(); // si la precarga ya llegó, se reemplaza antes de pintar: no se ve
    const resultado = await (previa ?? pedir(anio, mes));
    estado = resultado.ok ? "listo" : "error";
    if (resultado.ok) mostrarAnalisis(resultado.datos, nombreMes);
    else mostrarError(resultado.mensaje);
  }

  function precargar() {
    const { anio, mes } = raiz.dataset;
    const clave = `${anio}-${mes}`;
    if (estado !== "nuevo" || precarga?.clave === clave) return;
    const actual = { clave, resultado: null };
    actual.promesa = pedir(anio, mes).then((resultado) => (actual.resultado = resultado));
    precarga = actual;
  }

  const programarPrecarga = () => {
    clearTimeout(temporizador);
    temporizador = setTimeout(precargar, RETARDO_PRECARGA);
  };
  const cancelarPrecarga = () => clearTimeout(temporizador);

  // Solo ratón: en táctil el toque ya es el clic y no hay nada que adelantar.
  boton.addEventListener("pointerenter", (event) => {
    if (event.pointerType === "mouse") programarPrecarga();
  });
  boton.addEventListener("pointerleave", (event) => {
    if (event.pointerType === "mouse") cancelarPrecarga();
  });
  boton.addEventListener("focus", programarPrecarga);
  boton.addEventListener("blur", cancelarPrecarga);

  // Se pide una sola vez: si se cierra y se vuelve a abrir, se ve lo mismo sin gastar otra consulta.
  raiz.addEventListener("desplegable:abierto", () => {
    cancelarPrecarga();
    if (estado === "nuevo") cargar({ reutilizar: true });
  });
})();
