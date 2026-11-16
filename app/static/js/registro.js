/*
 * Formulario para crear una cuenta (lo común con el login está en acceso-form.js). Las reglas son
 * las mismas que revisa el servidor (app/services/usuarios.py); aquí solo responden al instante.
 *
 * Contrato con el backend (app/api/auth.py):
 *   POST /api/v1/auth/registro   {"nombre": str, "email": str, "password": str}
 *   201 -> cuenta creada y sesión abierta, se redirige a data-redirect
 *   422 {"errores": {campo: mensaje}} -> cada mensaje bajo su campo
 *   429 -> demasiados intentos
 */
(() => {
  const form = document.querySelector("[data-registro-form]");
  if (!form || !window.AccesoForm) return;

  const nombre = form.elements.nombre;
  const email = form.elements.email;
  const password = form.elements.password;
  const campos = [nombre, email, password];

  const MIN_PASSWORD = 8;
  const MAX_PASSWORD = 128;
  const MAX_NOMBRE = 100;
  const MESSAGES = {
    nombreMissing: "Escribe tu nombre.",
    nombreLong: `El nombre puede tener hasta ${MAX_NOMBRE} caracteres.`,
    emailMissing: "Escribe tu correo electrónico.",
    emailInvalid: "Revisa el correo. Debe verse así: nombre@correo.com",
    passwordShort: `La contraseña debe tener al menos ${MIN_PASSWORD} caracteres.`,
    passwordLong: `La contraseña puede tener hasta ${MAX_PASSWORD} caracteres.`,
    tooMany: "Hiciste demasiados intentos. Espera unos minutos antes de volver a intentar.",
    network: "No hay conexión con el servidor. Revisa tu internet e intenta de nuevo.",
    generic: "No pudimos crear tu cuenta. Intenta de nuevo en unos minutos.",
  };

  const ui = AccesoForm.crear(form, {
    campos,
    textoCargando: "Creando cuenta…",
    textoNormal: "Crear cuenta",
  });

  function validate() {
    const errors = [];
    const nombreValue = nombre.value.trim();
    const emailValue = email.value.trim();
    // La contraseña se cuenta por caracteres, como en el servidor (no por unidades UTF-16).
    const largo = [...password.value].length;
    if (!nombreValue) errors.push([nombre, MESSAGES.nombreMissing]);
    else if ([...nombreValue].length > MAX_NOMBRE) errors.push([nombre, MESSAGES.nombreLong]);
    if (!emailValue) errors.push([email, MESSAGES.emailMissing]);
    else if (!AccesoForm.EMAIL_PATTERN.test(emailValue)) errors.push([email, MESSAGES.emailInvalid]);
    if (largo < MIN_PASSWORD) errors.push([password, MESSAGES.passwordShort]);
    else if (largo > MAX_PASSWORD) errors.push([password, MESSAGES.passwordLong]);

    campos.forEach((input) => ui.setFieldError(input, null));
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
          nombre: nombre.value.trim(),
          email: email.value.trim().toLowerCase(),
          password: password.value,
        }),
      });

      if (response.ok) {
        ui.setSuccess();
        ui.goAfterCheck(form.dataset.redirect || "/resumen");
        return;
      }

      ui.shake();
      if (response.status === 422) {
        const errores = (await response.json().catch(() => ({}))).errores || {};
        const conError = campos.filter((input) => errores[input.name]);
        conError.forEach((input) => ui.setFieldError(input, errores[input.name]));
        if (conError.length) conError[0].focus();
        else ui.showAlert(MESSAGES.generic);
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
