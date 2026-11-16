/*
 * Presupuestos: tocar un día del calendario muestra sus gastos al lado. Los datos de
 * cada día vienen en <script type="application/json" data-dias> (los arma la vista en Python).
 */
(() => {
  const cal = document.querySelector("[data-calendario]");
  if (!cal) return;

  const { inicial, dias } = JSON.parse(cal.querySelector("[data-dias]").textContent);
  const vacio = cal.querySelector("[data-detalle-vacio]");
  const contenido = cal.querySelector("[data-detalle-contenido]");
  const titulo = cal.querySelector("[data-detalle-titulo]");
  const total = cal.querySelector("[data-detalle-total]");
  const lista = cal.querySelector("[data-detalle-lista]");

  function fila(item) {
    const li = document.createElement("li");
    const nombre = document.createElement("span");
    nombre.className = "rows__name";
    const texto = document.createElement("span");
    texto.textContent = item.descripcion;
    const sub = document.createElement("span");
    sub.className = "sub";
    sub.textContent = item.descripcion === item.categoria ? item.cuenta : `${item.categoria} · ${item.cuenta}`;
    texto.append(sub);
    nombre.append(texto);
    const monto = document.createElement("span");
    monto.className = "num";
    monto.textContent = item.monto;
    li.append(nombre, monto);
    return li;
  }

  function mostrar(iso) {
    const dia = dias[iso];
    if (!dia) return;
    for (const b of cal.querySelectorAll("[data-dia]")) {
      b.setAttribute("aria-pressed", String(b.dataset.dia === iso));
    }
    titulo.textContent = dia.titulo;
    total.textContent = dia.total;
    lista.replaceChildren(...dia.items.map(fila));
    vacio.hidden = true;
    contenido.hidden = false;
  }

  cal.addEventListener("click", (event) => {
    const boton = event.target.closest("[data-dia]");
    if (boton) mostrar(boton.dataset.dia);
  });

  if (inicial) mostrar(inicial);
})();
