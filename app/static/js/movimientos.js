/*
 * Sección Movimientos.
 * - Filtros: se aplican solos (selects y tipo al cambiar; búsqueda 300 ms después de escribir).
 *   Sin JS funciona igual con el botón "Filtrar". Los parámetros vacíos no se ponen en la URL.
 * - Celular: el panel "Filtros · N" empieza cerrado.
 * - Filas: abren el diálogo en modo edición (Enter o Espacio con teclado). Las de pagos de
 *   tarjeta abren el diálogo de pago.
 * - ?nuevo=1 abre el diálogo y ?guardado=<id> resalta la fila guardada.
 */
(() => {
  const form = document.querySelector("[data-filtros]");
  const lista = document.querySelector("[data-lista]");
  const ENFOCAR = "enfocar-busqueda";
  const reducido = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- Filtros ----------
  if (form) {
    const aplicar = () => {
      const params = new URLSearchParams();
      for (const [clave, valor] of new FormData(form)) {
        if (String(valor).trim()) params.set(clave, String(valor).trim());
      }
      location.assign(`${form.action}?${params}`);
    };

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      aplicar();
    });

    for (const control of form.querySelectorAll("select, input[type=radio]")) {
      control.addEventListener("change", aplicar);
    }

    const buscar = form.elements.q;
    let espera;
    buscar.addEventListener("input", () => {
      clearTimeout(espera);
      espera = setTimeout(() => {
        sessionStorage.setItem(ENFOCAR, "1");
        aplicar();
      }, 300);
    });

    // Después de buscar, el cursor vuelve al final de la búsqueda para seguir escribiendo.
    if (sessionStorage.getItem(ENFOCAR)) {
      sessionStorage.removeItem(ENFOCAR);
      buscar.focus();
      buscar.setSelectionRange(buscar.value.length, buscar.value.length);
    }

    // Al volver con Atrás desde la bfcache, los controles pueden quedar con lo último que se eligió
    // y la lista no. reset() los devuelve a lo que pintó el servidor, que coincide con la lista.
    window.addEventListener("pageshow", (event) => {
      if (event.persisted) form.reset();
    });

    const mas = form.querySelector("[data-filtros-mas]");
    if (mas && matchMedia("(max-width: 760px)").matches) mas.open = false;
  }

  // ---------- Filas que abren el diálogo ----------
  const editar = (fila) => window.dialogoMovimiento?.abrir(JSON.parse(fila.dataset.movimiento));

  for (const fila of document.querySelectorAll("[data-movimiento]")) {
    const datos = JSON.parse(fila.dataset.movimiento);
    fila.setAttribute("role", "button");
    fila.setAttribute("tabindex", "0");
    fila.setAttribute("aria-haspopup", "dialog");
    fila.setAttribute("aria-label", `Editar ${datos.nombre}`);
    fila.addEventListener("click", () => editar(fila));
    fila.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        editar(fila);
      }
    });
  }

  // Pagos de tarjeta: abren el diálogo de pago en modo edición (pago-dialogo.js).
  for (const fila of document.querySelectorAll("[data-pago]")) {
    const datos = JSON.parse(fila.dataset.pago);
    const abrir = () => window.dialogoPago?.abrir({ tarjetaId: datos.tarjeta_id, pago: datos });
    fila.setAttribute("role", "button");
    fila.setAttribute("tabindex", "0");
    fila.setAttribute("aria-haspopup", "dialog");
    fila.setAttribute("aria-label", `Editar ${datos.nombre}`);
    fila.addEventListener("click", abrir);
    fila.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        abrir();
      }
    });
  }

  if (!lista) return;

  // ---------- ?nuevo=1 y ?guardado=<id> ----------
  const url = new URL(location.href);

  if (lista.hasAttribute("data-abrir-dialogo")) {
    window.dialogoMovimiento?.abrir(null);
    url.searchParams.delete("nuevo");
  }

  const guardado = lista.dataset.guardado;
  if (guardado) {
    const fila = lista.querySelector(`[data-id="${CSS.escape(guardado)}"]`);
    if (fila) {
      fila.classList.add("is-saved");
      fila.scrollIntoView({ block: "center", behavior: reducido ? "auto" : "smooth" });
    }
    url.searchParams.delete("guardado");
  }

  // Quitar los parámetros de un solo uso para que recargar no vuelva a abrir o resaltar.
  if (url.href !== location.href) history.replaceState(null, "", url);
})();
