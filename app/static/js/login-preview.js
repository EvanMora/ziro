/*
 * Vista previa decorativa del login: cifra del saldo que cuenta hacia arriba, reflejo del
 * vidrio que sigue al cursor y una leve profundidad (parallax). Nada de esto se ejecuta si
 * el sistema pide reducir el movimiento.
 */
(() => {
  const stage = document.querySelector("[data-preview-stage]");
  const preview = stage && stage.querySelector(".preview");
  // Mismo corte con el que login.css oculta la vista previa, sin forzar el cálculo de estilos.
  if (!preview || window.matchMedia("(max-width: 1180px)").matches) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const counter = preview.querySelector("[data-count-to]");
  if (counter) {
    const target = Number(counter.dataset.countTo);
    const format = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 });
    const duration = 900;
    const delay = 300;
    let start;
    const tick = (now) => {
      start ??= now;
      const t = Math.min(Math.max(now - start - delay, 0) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      counter.textContent = `$${format.format(Math.round(target * eased))}`;
      if (t < 1) requestAnimationFrame(tick);
    };
    counter.textContent = "$0";
    requestAnimationFrame(tick);
  }

  if (!window.matchMedia("(pointer: fine)").matches) return;

  const panels = [...preview.querySelectorAll(".glass")];

  // Medidas guardadas: se leen solo cuando algo las invalida, nunca dentro del frame.
  let box = null;
  let border = [0, 0];
  let offsets = [];
  let dirty = true;
  const invalidate = () => { dirty = true; };

  // Posición del panel dentro del escenario, sin transformaciones (entrada ni parallax).
  const offsetIn = (el) => {
    let x = 0;
    let y = 0;
    for (let node = el; node && node !== stage; node = node.offsetParent) {
      x += node.offsetLeft;
      y += node.offsetTop;
    }
    return [x, y];
  };

  const measure = () => {
    box = stage.getBoundingClientRect();
    border = [stage.clientLeft, stage.clientTop];
    offsets = panels.map(offsetIn);
    dirty = false;
  };

  window.addEventListener("resize", invalidate);
  window.addEventListener("scroll", invalidate, { passive: true });
  stage.addEventListener("pointerenter", invalidate);

  let frame = 0;
  let clientX = 0;
  let clientY = 0;

  // En el frame solo se escribe.
  const paint = () => {
    frame = 0;
    const px = (clientX - box.left) / box.width - 0.5;
    const py = (clientY - box.top) / box.height - 0.5;
    preview.style.setProperty("--px", px.toFixed(3));
    preview.style.setProperty("--py", py.toFixed(3));
    // Las columnas se desplazan con el parallax (login.css: --px * -10px, --py * -8px).
    const left = box.left + border[0] + px * -10;
    const top = box.top + border[1] + py * -8;
    panels.forEach((panel, i) => {
      panel.style.setProperty("--glare-x", `${clientX - left - offsets[i][0]}px`);
      panel.style.setProperty("--glare-y", `${clientY - top - offsets[i][1]}px`);
    });
  };

  stage.addEventListener("pointermove", (event) => {
    // Se mide aquí, antes de las escrituras del frame, así la lectura no fuerza estilos.
    if (dirty) measure();
    clientX = event.clientX;
    clientY = event.clientY;
    frame ||= requestAnimationFrame(paint);
  }, { passive: true });

  stage.addEventListener("pointerleave", () => {
    cancelAnimationFrame(frame);
    frame = 0;
    preview.style.removeProperty("--px");
    preview.style.removeProperty("--py");
    for (const panel of panels) {
      panel.style.removeProperty("--glare-x");
      panel.style.removeProperty("--glare-y");
    }
  });
})();
