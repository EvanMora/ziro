/*
 * Formulario de inicio de sesión.
 *
 * Contrato esperado con el backend (pendiente de implementar):
 *   POST /api/v1/auth/login   {"email": str, "password": str, "recordar": bool}
 *   2xx -> sesión iniciada, se redirige a data-redirect
 *   400/401 -> credenciales incorrectas
 *   429 -> demasiados intentos
 */
(() => {
  const form = document.querySelector("[data-login-form]");
  if (!form) return;

  const email = form.elements.email;
  const password = form.elements.password;
  const remember = form.elements.recordar;
  const submit = form.querySelector("[type=submit]");
  const submitLabel = submit.querySelector("[data-label]");
  const alertBox = form.querySelector("[data-form-alert]");
  const toggle = form.querySelector("[data-toggle-password]");
  const capsHint = form.querySelector("[data-caps-hint]");
  const card = form.closest("[data-login-card]");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Si venimos de un intento fallido con Google (/login?error=...), mostrar el aviso de error.
  const GOOGLE_ERRORS = {
    google: "No pudimos iniciar sesión con Google. Revisa los permisos e intenta de nuevo.",
    google_no_configurado: "El inicio con Google no está disponible en este servidor.",
  };
  const errorParam = new URLSearchParams(window.location.search).get("error");
  if (errorParam && GOOGLE_ERRORS[errorParam]) {
    showAlert(GOOGLE_ERRORS[errorParam]);
  }


  const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const MESSAGES = {
    emailMissing: "Escribe tu correo electrónico.",
    emailInvalid: "Revisa el correo. Debe verse así: nombre@correo.com",
    passwordMissing: "Escribe tu contraseña.",
    credentials: "El correo o la contraseña no son correctos. Revísalos e intenta de nuevo.",
    tooMany: "Hiciste demasiados intentos. Espera unos minutos antes de volver a intentar.",
    network: "No hay conexión con el servidor. Revisa tu internet e intenta de nuevo.",
    generic: "No pudimos iniciar sesión. Intenta de nuevo en unos minutos.",
  };

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

  function validate() {
    const errors = [];
    const emailValue = email.value.trim();
    if (!emailValue) errors.push([email, MESSAGES.emailMissing]);
    else if (!EMAIL_PATTERN.test(emailValue)) errors.push([email, MESSAGES.emailInvalid]);
    if (!password.value) errors.push([password, MESSAGES.passwordMissing]);

    setFieldError(email, null);
    setFieldError(password, null);
    errors.forEach(([input, message]) => setFieldError(input, message));
    return errors;
  }

  function setLoading(loading) {
    submit.disabled = loading;
    submit.classList.toggle("is-loading", loading);
    submit.setAttribute("aria-busy", String(loading));
    submitLabel.textContent = loading ? "Iniciando sesión…" : "Iniciar sesión";
    card?.classList.toggle("is-busy", loading);
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

  function setSuccess() {
    submit.classList.remove("is-loading");
    submit.classList.add("is-success");
    submitLabel.textContent = "¡Listo!";
    card?.classList.remove("is-busy");
    card?.classList.add("is-done");
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
      if (document.activeElement === document.body || !document.activeElement) email.focus();
    });
  }

  // Corregir un campo borra su error al momento; no hace falta volver a enviar.
  [email, password].forEach((input) => {
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

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showAlert("");

    const errors = validate();
    if (errors.length) {
      errors[0][0].focus();
      shake();
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          email: email.value.trim(),
          password: password.value,
          recordar: remember.checked,
        }),
      });

      if (response.ok) {
        setSuccess();
        goAfterCheck(form.dataset.redirect || "/resumen");
        return;
      }

      shake();
      if (response.status === 400 || response.status === 401) {
        showAlert(MESSAGES.credentials);
        password.value = "";
        password.focus();
      } else if (response.status === 429) {
        showAlert(MESSAGES.tooMany);
      } else {
        showAlert(MESSAGES.generic);
      }
    } catch {
      shake();
      showAlert(MESSAGES.network);
    }
    setLoading(false);
  });
})();
