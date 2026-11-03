"""Evaluar por categoria que pasa con los datos de quien pide eliminar su cuenta (respuesta legal, E3 paso 3).

Reutiliza las reglas de ``mensajes.supresion`` (la misma que aplica el borrado): lo que aqui se muestra es lo
que ``suprimir_cuenta`` hara. Ademas calcula lo que *impide eliminar hoy*: mientras haya una clase por dictar
o un paquete pagado sin usar, borrar la cuenta le quitaria al usuario (y al profesor) algo que ya se pago.

Solo los alumnos tienen evaluador: profesores y apoderados guardan mas datos propios (documentos, cuenta
bancaria) y primero hay que definir como se seudonimizan. Mientras tanto la solicitud se recibe, pero no se ejecuta.
"""

from dataclasses import dataclass

from django.utils import timezone

from alumnos.models import Inscripcion
from alumnos.roles import ALUMNO, resolver_rol
from mensajes import supresion
from notificaciones.models import Notificacion
from soporte.models import Ticket

ELIMINA, CONSERVA = 'elimina', 'conserva'


@dataclass(frozen=True)
class Categoria:
    nombre: str
    accion: str   # ELIMINA o CONSERVA
    detalle: str


@dataclass(frozen=True)
class Evaluacion:
    categorias: tuple
    bloqueos: tuple   # razones por las que hoy no se puede eliminar; vacio si se puede

    @property
    def puede(self):
        return not self.bloqueos

    @property
    def conserva_algo(self):
        return any(c.accion == CONSERVA for c in self.categorias)


def _bloqueos_comunes(user, ticket):
    """Otros tickets abiertos del usuario: hay una gestion en curso que se perderia al borrar la cuenta."""
    abiertos = Ticket.objects.filter(autor=user, estado=Ticket.ABIERTO)
    if ticket is not None:
        abiertos = abiertos.exclude(pk=ticket.pk)
    n = abiertos.count()
    return [f'Tiene {n} ticket(s) de soporte abierto(s) además de esta solicitud: hay que resolverlos antes.'] if n else []


def _alumno(user, ticket):
    alumno = user.perfil_alumno
    ahora = timezone.now()
    bloqueos = _bloqueos_comunes(user, ticket)
    por_dictar = Inscripcion.objects.filter(alumno=alumno, estado__in=Inscripcion.ESTADOS_ACTIVOS,
                                            sesion__fecha_hora_inicio__gt=ahora).count()
    if por_dictar:
        bloqueos.append(f'Tiene {por_dictar} clase(s) reservada(s) por dictar: hay que cancelarlas o esperar a que pasen.')
    sin_usar = sum(p.clases_disponibles for p in alumno.paquetes.vigentes())
    if sin_usar:
        bloqueos.append(f'Tiene {sin_usar} clase(s) pagada(s) sin usar en paquetes vigentes: se perderían.')
    if alumno.suscripciones.vigentes().exists():
        bloqueos.append('Tiene un plan pagado todavía vigente.')

    conservadas = supresion.conversaciones_conservadas(user).count()
    normales = supresion.conversaciones_de(user).count() - conservadas
    historial = supresion.tiene_historial(user)
    categorias = [Categoria('Datos de la cuenta', ELIMINA,
                            'Nombre, correo, RUT, teléfono, dirección, fecha de nacimiento, género y foto.')]
    if normales:
        categorias.append(Categoria('Conversaciones con profesores', ELIMINA, f'{normales} conversación(es) y sus mensajes.'))
    if conservadas:
        categorias.append(Categoria(
            'Conversaciones reportadas', CONSERVA,
            f'{conservadas} conversación(es) reportada(s): se conservan solo para soporte mientras se revisan. '
            'La otra persona deja de verlas.'))
    if Notificacion.objects.filter(usuario=user).exists():
        categorias.append(Categoria('Avisos de la plataforma', ELIMINA, 'Tus notificaciones.'))
    if historial:
        categorias.append(Categoria(
            'Pagos y clases', CONSERVA,
            'Tus pagos, paquetes y clases, sin tus datos personales: son el registro de lo que se le pagó al profesor '
            'y de la contabilidad. Cuánto tiempo se guardan está por definir con el contador.'))
    if conservadas or historial:  # la cuenta no se borra: queda seudonimizada y con ella sus tickets
        categorias.append(Categoria('Tickets de soporte', CONSERVA,
                                    'Quedan en la cuenta eliminada; solo soporte los puede leer.'))
    return Evaluacion(tuple(categorias), tuple(bloqueos))


EVALUADORES = {ALUMNO.clave: _alumno}


def evaluar(user, ticket=None):
    """Que pasaria hoy con la cuenta de ``user``. ``ticket``: el de su solicitud (no cuenta como gestion abierta)."""
    rol, _ = resolver_rol(user)
    evaluador = EVALUADORES.get(rol.clave) if rol else None
    if evaluador is None:
        etiqueta = rol.etiqueta.lower() if rol else 'esta cuenta'
        return Evaluacion((), (f'Todavía no se puede eliminar automáticamente una cuenta de {etiqueta}: '
                               'sus datos propios (documentos, cuenta bancaria) aún no tienen regla de conservación.',))
    return evaluador(user, ticket)
