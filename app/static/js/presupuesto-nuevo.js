/*
 * Crear presupuesto: un monto por categoría, el total se suma mientras se escribe y se guarda con
 *   PUT /api/v1/presupuestos/<anio>/<mes>   {"montos": [{"categoria_id": 3, "monto": "450000"}]}
 * 200 -> vuelve a la pantalla de origen con un aviso; 422 -> {"errores": {"general" | "monto_<id>": mensaje}}.
 */
(() => {
  const form = document.querySelector("[data-presupuesto-form]");
  if (!form) return;

  const entradas = [...form.querySelectorAll("[data-monto]")];
  const total = form.querySelector("[data-total]");
  const general = form.querySelector("[data-error-general]");
  const guardar = form.querySelector("[data-guardar]");
  const etiqueta = guardar.querySelector("[data-label]").textContent;

  const digitos = (texto) => String(texto).replace(/\D/g, "").replace(/^0+(?=\d)/, "");
  const miles = (d) => d.replace(/\B(?=(\d{3})+(?!\d))/g, ".");

  function sumar() {
    const suma = entradas.reduce((acc, e) => acc + Number(digitos(e.value) || 0), 0);
    total.textContent = `$${miles(String(suma))}`;
  }

  function limpiarError(entrada) {
    const msg = document.getElementById(entrada.getAttribute("aria-describedby"));
    msg.hidden = true;
    entrada.removeAttribute("aria-invalid");
  }

  for (const entrada of entradas) {
    entrada.addEventListener("input", () => {
      const d = digitos(entrada.value).slice(0, 12);
      entrada.value = d && d !== "0" ? miles(d) : "";
      limpiarError(entrada);
      general.hidden = true;
      sumar();
    });
  }

  form.addEventListener("click", (event) => {
    const boton = event.target.closest("[data-usar]");
    if (!boton) return;
    const entrada = document.getElementById(boton.dataset.para);
    entrada.value = boton.dataset.usar;
    entrada.dispatchEvent(new Event("input"));
    entrada.focus();
  });

  function mostrarErrores(errores) {
    let primero = null;
    for (const [campo, mensaje] of Object.entries(errores)) {
      const entrada = campo.startsWith("monto_") && form.querySelector(`[data-categoria="${CSS.escape(campo.slice(6))}"]`);
      if (entrada) {
        const msg = document.getElementById(entrada.getAttribute("aria-describedby"));
        msg.textContent = mensaje;
        msg.hidden = false;
        entrada.setAttribute("aria-invalid", "true");
        primero ??= entrada;
      } else {
        general.textContent = mensaje;
        general.hidden = false;
      }
    }
    (primero ?? general).focus?.();
  }

  function ocupar(si) {
    guardar.classList.toggle("is-loading", si);
    guardar.disabled = si;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (guardar.disabled) return;
    general.hidden = true;
    const montos = entradas
      .map((e) => ({ categoria_id: Number(e.dataset.categoria), monto: digitos(e.value) }))
      .filter((m) => Number(m.monto) > 0);
    if (!montos.length) {
      mostrarErrores({ general: "Ponle un monto al menos a una categoría." });
      return;
    }

    ocupar(true);
    try {
      const r = await fetch(`/api/v1/presupuestos/${form.dataset.anio}/${form.dataset.mes}`, {
        method: "PUT",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ montos }),
      });
      if (r.ok) {
        // El aviso lo muestra app-shell.js en la página de origen.
        const volver = new URL(form.dataset.volver, location.href);
        volver.searchParams.set("aviso", etiqueta === "Crear presupuesto" ? "presupuesto-creado" : "presupuesto-guardado");
        location.assign(volver);
        return;
      }
      const datos = await r.json().catch(() => ({}));
      mostrarErrores(datos.errores ?? { general: "No se pudo guardar. Inténtalo de nuevo." });
    } catch {
      mostrarErrores({ general: "No se pudo guardar. Revisa tu conexión e inténtalo de nuevo." });
    }
    ocupar(false);
  });

  // Al volver con Atrás, el navegador puede restaurar la página con el botón ocupado.
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) ocupar(false);
  });

  sumar();
})();
