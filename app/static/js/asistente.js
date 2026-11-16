/*
 * Asistente de Movimientos (menú "✦ Asistente ▾" de la barra superior; abrir y cerrar lo maneja
 * desplegable.js).
 * - Los ejemplos llenan la frase. "Completar" la manda a Gemini (window.dialogoMovimiento.interpretar)
 *   y, si sale bien, cierra el menú y abre "Nuevo movimiento" ya lleno para revisar y guardar.
 */
(() => {
  const raiz = document.querySelector("[data-asistente]");
  if (!raiz) return;

  const form = raiz.querySelector("[data-asistente-form]");
  const texto = raiz.querySelector("[data-asistente-texto]");
  const completar = raiz.querySelector("[data-asistente-completar]");
  const mensaje = raiz.querySelector("[data-asistente-mensaje]");
  let peticion = 0; // si se cierra el menú mientras Gemini responde, esa respuesta se ignora

  function mostrarMensaje(contenido, error = false) {
    mensaje.textContent = contenido || "";
    mensaje.hidden = !contenido;
    mensaje.classList.toggle("field__message--error", error);
    if (error) texto.setAttribute("aria-invalid", "true");
    else texto.removeAttribute("aria-invalid");
  }

  function ocupar(si) {
    completar.classList.toggle("is-loading", si);
    completar.disabled = si;
  }

  raiz.addEventListener("desplegable:abierto", () => texto.focus());
  raiz.addEventListener("desplegable:cerrado", () => {
    peticion += 1;
    ocupar(false);
    mostrarMensaje(null);
  });

  for (const ejemplo of raiz.querySelectorAll("[data-ejemplo]")) {
    ejemplo.addEventListener("click", () => {
      texto.value = ejemplo.textContent.trim();
      mostrarMensaje(null);
      texto.focus();
    });
  }

  texto.addEventListener("input", () => {
    if (texto.hasAttribute("aria-invalid")) mostrarMensaje(null);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (completar.disabled) return;
    const frase = texto.value.trim();
    if (!frase) {
      mostrarMensaje("Escribe qué gastaste o recibiste.", true);
      texto.focus();
      return;
    }
    const dialogo = window.dialogoMovimiento;
    if (!dialogo?.interpretar) return;

    const esta = ++peticion;
    mostrarMensaje(null);
    ocupar(true);
    const { sugerencia, error } = await dialogo.interpretar(frase);
    if (esta !== peticion) return;
    ocupar(false);
    if (error) {
      mostrarMensaje(error, true);
      texto.focus();
      return;
    }
    raiz.desplegable.cerrar();
    texto.value = "";
    dialogo.abrirConSugerencia(frase, sugerencia);
  });
})();
