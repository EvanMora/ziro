"""Límite de intentos para el login y el registro (contra adivinar contraseñas a fuerza bruta), y el
almacén de momentos que también usa el límite de consultas a la IA (app/services/ia.py).

Cuenta intentos por clave (p. ej. "correo:ana@x.com" o "ip:10.0.0.1") dentro de una ventana de tiempo.
Se guardan en la tabla `intentos` (app/models/intentos.py), no en la memoria del proceso: desplegada,
la app corre en varias instancias que se prenden y se apagan, y el límite tiene que ser uno solo.

Contar y registrar son dos pasos: dos peticiones simultáneas pueden pasar las dos con el último cupo.
Para un límite contra fuerza bruta, uno o dos intentos de más no cambian nada.
"""
import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.models.intentos import MAX_CLAVE, IntentoDB
from app.services import database

# Lo que se conserva de cada clave: ninguna ventana pasa de un día.
CONSERVAR = timedelta(days=1)


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def _utc(momento: datetime) -> datetime:
    """SQLite devuelve los momentos sin zona; siempre se guardan en UTC."""
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def _clave(espacio: str, clave: str) -> str:
    """La clave como se guarda: "<espacio>:<clave>". Si no cabe en la columna (el correo del login no
    tiene tope) o trae un carácter nulo (Postgres no lo acepta), va su hash."""
    completa = f"{espacio}:{clave}"
    if len(completa) > MAX_CLAVE or "\x00" in completa:
        completa = f"{espacio}:sha256:{hashlib.sha256(clave.encode('utf-8', 'surrogatepass')).hexdigest()}"
    return completa


def momentos(clave: str, desde: datetime) -> list[datetime]:
    """Los momentos de la clave posteriores a `desde`, del más viejo al más nuevo."""
    with database.sesion() as db:
        filas = db.execute(
            select(IntentoDB.momento).where(IntentoDB.clave == clave, IntentoDB.momento > desde)
            .order_by(IntentoDB.momento, IntentoDB.id)
        ).scalars().all()
        return [_utc(m) for m in filas]


def anotar(clave: str, momento: datetime) -> None:
    """Guarda un intento de la clave y, de paso, borra los suyos de hace más de un día, para que la
    tabla no crezca sin fin."""
    with database.sesion() as db:
        db.execute(delete(IntentoDB).where(IntentoDB.clave == clave, IntentoDB.momento <= momento - CONSERVAR))
        db.add(IntentoDB(clave=clave, momento=momento))


def borrar(clave: str) -> None:
    with database.sesion() as db:
        db.execute(delete(IntentoDB).where(IntentoDB.clave == clave))


def borrar_espacio(espacio: str) -> None:
    """Borra todas las claves de un espacio ("login", "registro", "ia")."""
    with database.sesion() as db:
        db.execute(delete(IntentoDB).where(IntentoDB.clave.startswith(f"{espacio}:", autoescape=True)))


class LimiteIntentos:
    """Bloquea una clave cuando acumula `maximo` intentos registrados dentro de `ventana`. `nombre` es
    su espacio en la tabla: dos límites con el mismo nombre (en dos instancias) comparten la cuenta."""

    def __init__(self, nombre: str, maximo: int, ventana: timedelta):
        self.nombre = nombre
        self.maximo = maximo
        self.ventana = ventana

    def bloqueado(self, clave: str) -> bool:
        with database.sesion() as db:
            cuantos = db.execute(
                select(func.count(IntentoDB.id)).where(
                    IntentoDB.clave == _clave(self.nombre, clave), IntentoDB.momento > ahora() - self.ventana)
            ).scalar_one()
        return cuantos >= self.maximo

    def registrar(self, clave: str) -> None:
        anotar(_clave(self.nombre, clave), ahora())

    def limpiar(self, clave: str) -> None:
        borrar(_clave(self.nombre, clave))

    def reiniciar(self) -> None:
        borrar_espacio(self.nombre)


# Login: 5 fallos por correo y 5 por IP en 15 minutos. Registro: 5 intentos por IP por hora.
LOGIN = LimiteIntentos("login", 5, timedelta(minutes=15))
REGISTRO = LimiteIntentos("registro", 5, timedelta(hours=1))


def reiniciar_todos() -> None:
    """Solo para tests."""
    LOGIN.reiniciar()
    REGISTRO.reiniciar()
