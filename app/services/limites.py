"""Límite de intentos para el login y el registro (contra adivinar contraseñas a fuerza bruta).

Cuenta intentos por clave (p. ej. "correo:ana@x.com" o "ip:10.0.0.1") dentro de una ventana de tiempo.
Vive en la memoria del proceso, como el límite de la IA: se pierde al reiniciar y no se comparte entre
varios procesos, que es suficiente para una sola instancia de la app.
"""
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock


def ahora() -> datetime:
    return datetime.now(timezone.utc)


class LimiteIntentos:
    """Bloquea una clave cuando acumula `maximo` intentos registrados dentro de `ventana`."""

    def __init__(self, maximo: int, ventana: timedelta):
        self.maximo = maximo
        self.ventana = ventana
        self._intentos: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = Lock()

    def _vigentes(self, clave: str) -> deque[datetime]:
        intentos = self._intentos[clave]
        limite = ahora() - self.ventana
        while intentos and intentos[0] <= limite:
            intentos.popleft()
        if not intentos:
            del self._intentos[clave]  # no acumular claves vacías en memoria
            return deque()
        return intentos

    def bloqueado(self, clave: str) -> bool:
        with self._lock:
            return len(self._vigentes(clave)) >= self.maximo

    def registrar(self, clave: str) -> None:
        with self._lock:
            self._vigentes(clave)
            self._intentos[clave].append(ahora())

    def limpiar(self, clave: str) -> None:
        with self._lock:
            self._intentos.pop(clave, None)

    def reiniciar(self) -> None:
        with self._lock:
            self._intentos.clear()


# Login: 5 fallos por correo y 5 por IP en 15 minutos. Registro: 5 intentos por IP por hora.
LOGIN = LimiteIntentos(5, timedelta(minutes=15))
REGISTRO = LimiteIntentos(5, timedelta(hours=1))


def reiniciar_todos() -> None:
    """Solo para tests."""
    LOGIN.reiniciar()
    REGISTRO.reiniciar()
