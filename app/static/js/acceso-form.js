/*
 * Lo que comparten los formularios de iniciar sesión (login.js) y de crear cuenta (registro.js):
 * errores por campo, aviso general, botón con spinner y check, sacudida de la tarjeta, mostrar la
 * contraseña, aviso de Bloq Mayús y el foco inicial.
 *
 *   const ui = AccesoForm.crear(form, { campos: [nombre, email, password], textoCargando, textoNormal });
 *   ui.setFieldError(input, "mensaje");  ui.showAlert("mensaje");  ui.setLoading(true);
 *   ui.setSuccess();  ui.goAfterCheck("/resumen");  ui.shake();
 */
window.AccesoForm = {
  EMAIL_PATTERN: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,

  crear(form, { campos, textoCargando, textoNormal }) {
    const submit = form.querySelector("[type=submit]");
    const submitLabel = submit.querySelector("[data-label]");
    const alertBox = form.querySelector("[data-form-alert]");
    const toggle = form.querySelector("[data-toggle-password]");
    const capsHint = form.querySelector("[data-caps-hint]");
    const password = form.elements.password;
    const card = form.closest("[data-login-card]");
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function setFieldError(input, message) {
      const error = document.getElementById(`${input.id}-error`);
      error.textContent = message || "";
      error.hidden = !message;
      if (message) input.setAttribute("aria-invalid", "true");
      else input.removeAttribute("aria-invalid");
    }

    function showAlert(message) {
      alertBox.textContent = message || "";
      alertBox.hidden = !message;
    }

    function setLoading(loading) {
      submit.disabled = loading;
      submit.classList.toggle("is-loading", loading);
      submit.setAttribute("aria-busy", String(loading));
      submitLabel.textContent = loading ? textoCargando : textoNormal;
      card?.classList.toggle("is-busy", loading);
    }

    function setSuccess() {
      submit.classList.remove("is-loading");
      submit.classList.add("is-success");
      submitLabel.textContent = "¡Listo!";
      card?.classList.remove("is-busy");
      card?.classList.add("is-done");
    }

    // Navega cuando termina de dibujarse el check (draw-check, 360 ms en styles.css).
    // Tope de seguridad por si animationend no llega; con movimiento reducido, sin espera.
    function goAfterCheck(url) {
      if (reduceMotion) {
        window.location.assign(url);
        return;
      }
      let gone = false;
      const go = () => {
        if (gone) return;
        gone = true;
        window.location.assign(url);
      };
      submit.querySelector(".btn__check")?.addEventListener("animationend", go, { once: true });
      setTimeout(go, 400);
    }

    // Sacudida breve de la tarjeta, solo al enviar con errores.
    function shake() {
      if (!card || reduceMotion) return;
      card.classList.remove("is-shaking");
      void card.offsetWidth; // reinicia la animación si se repite
      card.classList.add("is-shaking");
    }

    // Solo con mouse: en celulares el foco automático abre el teclado y tapa el titular.
    // En el siguiente frame, para no forzar el primer estilo y layout dentro de esta tarea.
    // Si la persona ya puso el foco en otro sitio, se respeta.
    if (window.matchMedia("(pointer: fine)").matches) {
      requestAnimationFrame(() => {
        if (document.activeElement === document.body || !document.activeElement) campos[0].focus();
      });
    }

    // Corregir un campo borra su error al momento; no hace falta volver a enviar.
    campos.forEach((input) => {
      input.addEventListener("input", () => {
        if (input.hasAttribute("aria-invalid")) setFieldError(input, null);
        if (!alertBox.hidden) showAlert(""); // no tocar el DOM en cada tecla si ya está oculta
      });
    });

    toggle.addEventListener("click", () => {
      const show = password.type === "password";
      password.type = show ? "text" : "password";
      toggle.classList.toggle("is-revealed", show);
      toggle.setAttribute("aria-label", show ? "Ocultar contraseña" : "Mostrar contraseña");
      password.focus();
    });

    card?.addEventListener("animationend", (event) => {
      if (event.animationName === "card-shake") card.classList.remove("is-shaking");
    });

    const updateCapsHint = (event) => {
      if (!event.getModifierState) return;
      const hidden = !event.getModifierState("CapsLock");
      if (capsHint.hidden !== hidden) capsHint.hidden = hidden;
    };
    password.addEventListener("keydown", updateCapsHint);
    password.addEventListener("keyup", updateCapsHint);
    password.addEventListener("blur", () => {
      capsHint.hidden = true;
    });

    return { setFieldError, showAlert, setLoading, setSuccess, goAfterCheck, shake };
  },
};
