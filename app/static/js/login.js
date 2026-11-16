/*
 * Formulario de inicio de sesión (lo común con el registro está en acceso-form.js).
 *
 * Contrato con el backend (app/api/auth.py):
 *   POST /api/v1/auth/login   {"email": str, "password": str, "recordar": bool}
 *   2xx -> sesión iniciada, se redirige a data-redirect
 *   400/401 -> credenciales incorrectas
 *   429 -> demasiados intentos
 */
(() => {
  const form = document.querySelector("[data-login-form]");
  if (!form || !window.AccesoForm) return;

  const email = form.elements.email;
  const password = form.elements.password;
  const remember = form.elements.recordar;

  const MESSAGES = {
    emailMissing: "Escribe tu correo electrónico.",
    emailInvalid: "Revisa el correo. Debe verse así: nombre@correo.com",
    passwordMissing: "Escribe tu contraseña.",
    credentials: "El correo o la contraseña no son correctos. Revísalos e intenta de nuevo.",
    tooMany: "Hiciste demasiados intentos. Espera unos minutos antes de volver a intentar.",
    network: "No hay conexión con el servidor. Revisa tu internet e intenta de nuevo.",
    generic: "No pudimos iniciar sesión. Intenta de nuevo en unos minutos.",
  };

  const ui = AccesoForm.crear(form, {
    campos: [email, password],
    textoCargando: "Iniciando sesión…",
    textoNormal: "Iniciar sesión",
  });

  function validate() {
    const errors = [];
    const emailValue = email.value.trim();
    if (!emailValue) errors.push([email, MESSAGES.emailMissing]);
    else if (!AccesoForm.EMAIL_PATTERN.test(emailValue)) errors.push([email, MESSAGES.emailInvalid]);
    if (!password.value) errors.push([password, MESSAGES.passwordMissing]);

    ui.setFieldError(email, null);
    ui.setFieldError(password, null);
    errors.forEach(([input, message]) => ui.setFieldError(input, message));
    return errors;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    ui.showAlert("");

    const errors = validate();
    if (errors.length) {
      errors[0][0].focus();
      ui.shake();
      return;
    }

    ui.setLoading(true);
    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          email: email.value.trim().toLowerCase(),
          password: password.value,
          recordar: remember.checked,
        }),
      });

      if (response.ok) {
        ui.setSuccess();
        ui.goAfterCheck(form.dataset.redirect || "/resumen");
        return;
      }

      ui.shake();
      if (response.status === 400 || response.status === 401) {
        ui.showAlert(MESSAGES.credentials);
        password.value = "";
        password.focus();
      } else if (response.status === 429) {
        ui.showAlert(MESSAGES.tooMany);
      } else {
        ui.showAlert(MESSAGES.generic);
      }
    } catch {
      ui.shake();
      ui.showAlert(MESSAGES.network);
    }
    ui.setLoading(false);
  });
})();
