/*
 * Barra lateral de la app.
 * - Escritorio: contraer / expandir. El estado se guarda en una cookie para que el servidor
 *   pinte la barra ya contraída en la siguiente página (con localStorage parpadearía).
 * - Celular: abre y cierra el cajón con el botón de menú, tocando fuera o con Esc.
 * - Si la sesión vence con la página abierta, la API responde 401: en vez de mostrar un error en el
 *   diálogo, se lleva a la persona al login.
 */
(() => {
  const fetchOriginal = window.fetch.bind(window);
  window.fetch = async (recurso, opciones) => {
    const respuesta = await fetchOriginal(recurso, opciones);
    const url = new URL(recurso instanceof Request ? recurso.url : String(recurso), location.href);
    if (respuesta.status === 401 && url.origin === location.origin && url.pathname.startsWith("/api/")) {
      window.location.assign("/login");
    }
    return respuesta;
  };
})();

// Cerrar sesión: borra la sesión en el servidor y vuelve al login (también si falla la red: el login
// con una sesión aún abierta lleva de nuevo al Resumen, así que nada se pierde).
(() => {
  const boton = document.querySelector("[data-logout]");
  if (!boton) return;
  boton.addEventListener("click", async () => {
    boton.disabled = true;
    try {
      await fetch("/api/v1/auth/logout", { method: "POST", credentials: "same-origin" });
    } finally {
      window.location.assign("/login");
    }
  });
})();

(() => {
  const shell = document.querySelector("[data-shell]");
  if (!shell) return;

  const COOKIE = "barra_contraida";
  const toggle = shell.querySelector("[data-collapse]");
  const toggleLabel = shell.querySelector("[data-collapse-label]");
  const menu = shell.querySelector("[data-menu]");
  const scrim = shell.querySelector("[data-scrim]");

  function alternarBarra() {
    const collapsed = shell.classList.toggle("is-collapsed");
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggleLabel.textContent = collapsed ? "Expandir barra" : "Contraer barra";
    document.cookie = `${COOKIE}=${collapsed ? 1 : 0}; path=/; max-age=31536000; SameSite=Lax`;
  }

  // Las columnas cambian de golpe y el paso lo anima una View Transition (clase vt-barra, ver
  // app.css). Sin la API o con movimiento reducido, cambia al instante.
  const raiz = document.documentElement;
  const reducido = matchMedia("(prefers-reduced-motion: reduce)");
  let transicion = null;

  toggle.addEventListener("click", () => {
    if (!document.startViewTransition || reducido.matches) return alternarBarra();
    raiz.classList.add("vt-barra");
    const actual = (transicion = document.startViewTransition(alternarBarra));
    // Con dos clics seguidos el primero se salta: solo quita la clase la última transición.
    actual.finished.finally(() => {
      if (transicion !== actual) return;
      transicion = null;
      raiz.classList.remove("vt-barra");
    });
  });

  function setDrawer(open) {
    shell.classList.toggle("is-open", open);
    menu.setAttribute("aria-expanded", String(open));
    if (open) shell.querySelector(".sb-item[aria-current]")?.focus();
    else if (shell.contains(document.activeElement)) menu.focus();
  }

  menu.addEventListener("click", () => setDrawer(true));
  scrim.addEventListener("click", () => setDrawer(false));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && shell.classList.contains("is-open")) setDrawer(false);
  });
})();

/*
 * Aviso tras guardar o eliminar (el "toast" de abajo). Quien guarda navega con ?aviso=<clave> en
 * la URL (movimiento-dialogo.js, cuentas.js, categorias.js, pago-dialogo.js,
 * presupuesto-nuevo.js); aquí se muestra el texto de esa clave y se quita de la URL para que
 * recargar o volver con Atrás no lo repita. Por la URL y no por sessionStorage: leer
 * sessionStorage en cada carga es una llamada síncrona al navegador (~2 ms). Solo se aceptan las
 * claves conocidas, así un enlace no puede mostrar un texto cualquiera.
 */
(() => {
  if (!location.search.includes("aviso=")) return;

  const AVISOS = {
    "movimiento-guardado": "Movimiento guardado",
    "movimiento-eliminado": "Movimiento eliminado",
    "cuenta-guardada": "Cuenta guardada",
    "cuenta-eliminada": "Cuenta eliminada",
    "categoria-guardada": "Categoría guardada",
    "categoria-eliminada": "Categoría eliminada",
    "pago-registrado": "Pago registrado",
    "pago-guardado": "Pago guardado",
    "pago-eliminado": "Pago eliminado",
    "presupuesto-creado": "Presupuesto creado",
    "presupuesto-guardado": "Presupuesto guardado",
    "meta-guardada": "Meta guardada",
    "meta-eliminada": "Meta eliminada",
    "aporte-guardado": "Aporte guardado",
    "retiro-guardado": "Retiro guardado",
    "aporte-eliminado": "Aporte borrado",
  };

  const url = new URL(location.href);
  const texto = AVISOS[url.searchParams.get("aviso")];
  url.searchParams.delete("aviso");
  history.replaceState(history.state, "", url);

  const toast = document.querySelector("[data-toast]");
  if (!toast || !texto) return;
  toast.textContent = texto;
  toast.hidden = false;
  setTimeout(() => {
    toast.hidden = true;
  }, 4000);
})();
