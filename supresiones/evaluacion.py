"""Evaluar por categoria que pasa con los datos de quien pide eliminar su cuenta (respuesta legal, E3 paso 3).

Reutiliza las reglas de ``mensajes.supresion`` (la misma que aplica el borrado): lo que aqui se muestra es lo
que ``suprimir_cuenta`` hara. Ademas calcula lo que *impide eliminar hoy*: mientras haya una clase por dictar
o un paquete pagado sin usar, borrar la cuenta le quitaria al usuario (y al profesor) algo que ya se pago.

Cada rol aporta sus bloqueos y sus datos propios; lo demas (conversaciones, avisos, tickets) es comun. El que no
tenga evaluador (admin, soporte) no se elimina automaticamente.
"""

from dataclasses import dataclass

from django.utils import timezone

from alumnos.models import Inscripcion, PaqueteClases, SolicitudRetiro
from alumnos.roles import ALUMNO, APODERADO, PROFESOR, resolver_rol
from alumnos.utils import es_menor
from apoderados.models import Vinculo
from mensajes import supresion
from notificaciones.models import Notificacion
from soporte.models import Ticket

ELIMINA, CONSERVA = 'elimina', 'conserva'
SIN_PLAZO = 'Cuánto tiempo se guardan está por definir con el contador.'


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


DATOS_CUENTA = Categoria('Datos de la cuenta', ELIMINA,
                         'Nombre, correo, RUT, teléfono, dirección, fecha de nacimiento, género y foto.')
HISTORIAL_ALUMNO = Categoria(
    'Pagos y clases', CONSERVA,
    'Tus pagos, paquetes y clases, sin tus datos personales: son el registro de lo que se le pagó al profesor '
    f'y de la contabilidad. {SIN_PLAZO}')
HISTORIAL_PROFESOR = Categoria(
    'Clases, pagos y retiros', CONSERVA,
    'Las clases dictadas, lo que se pagó por ellas y tus retiros, sin tus datos personales: son el registro de lo '
    f'que se pagó a alumnos y profesores y la contabilidad. {SIN_PLAZO}')
HISTORIAL_APODERADO = Categoria(
    'Compras y vínculos', CONSERVA,
    'Las compras de clases que pagaste y tus vínculos verificados con estudiantes, sin tus datos personales: son el '
    f'registro de lo que se pagó y de quién tuvo autoridad sobre un menor. {SIN_PLAZO}')


def _bloqueos_comunes(user, ticket):
    """Otros tickets abiertos del usuario: hay una gestion en curso que se perderia al borrar la cuenta."""
    abiertos = Ticket.objects.filter(autor=user, estado=Ticket.ABIERTO)
    if ticket is not None:
        abiertos = abiertos.exclude(pk=ticket.pk)
    n = abiertos.count()
    return [f'Tiene {n} ticket(s) de soporte abierto(s) además de esta solicitud: hay que resolverlos antes.'] if n else []


def _categorias(user, propias, con, historial):
    """Las categorias de todos los roles. ``propias`` abre la lista (datos de la cuenta y los propios del rol),
    ``con`` nombra a la otra parte de las conversaciones e ``historial`` es la categoria de lo que se conserva por
    la contabilidad o por otras personas: solo se muestra si la cuenta lo tiene."""
    conservadas = supresion.conversaciones_conservadas(user).count()
    normales = supresion.conversaciones_de(user).count() - conservadas
    conserva_historial = supresion.tiene_historial(user)
    categorias = list(propias)
    if normales:
        categorias.append(Categoria(f'Conversaciones con {con}', ELIMINA, f'{normales} conversación(es) y sus mensajes.'))
    if conservadas:
        categorias.append(Categoria(
            'Conversaciones reportadas', CONSERVA,
            f'{conservadas} conversación(es) reportada(s): se conservan solo para soporte mientras se revisan. '
            'La otra persona deja de verlas.'))
    if Notificacion.objects.filter(usuario=user).exists():
        categorias.append(Categoria('Avisos de la plataforma', ELIMINA, 'Tus notificaciones.'))
    if conserva_historial:
        categorias.append(historial)
    if conservadas or conserva_historial:  # la cuenta no se borra: queda seudonimizada y con ella sus tickets
        categorias.append(Categoria('Tickets de soporte', CONSERVA,
                                    'Quedan en la cuenta eliminada; solo soporte los puede leer.'))
    return tuple(categorias)


def _alumno(user, ticket):
    alumno = user.perfil_alumno
    bloqueos = _bloqueos_comunes(user, ticket)
    por_dictar = Inscripcion.objects.filter(alumno=alumno, estado__in=Inscripcion.ESTADOS_ACTIVOS,
                                            sesion__fecha_hora_inicio__gt=timezone.now()).count()
    if por_dictar:
        bloqueos.append(f'Tiene {por_dictar} clase(s) reservada(s) por dictar: hay que cancelarlas o esperar a que pasen.')
    sin_usar = sum(p.clases_disponibles for p in alumno.paquetes.vigentes())
    if sin_usar:
        bloqueos.append(f'Tiene {sin_usar} clase(s) pagada(s) sin usar en paquetes vigentes: se perderían.')
    if alumno.suscripciones.vigentes().exists():
        bloqueos.append('Tiene un plan pagado todavía vigente.')
    return Evaluacion(_categorias(user, [DATOS_CUENTA], 'profesores', HISTORIAL_ALUMNO), tuple(bloqueos))


def _profesor(user, ticket):
    from user_profesor.views import calcular_saldos, formato_clp  # el saldo se calcula en su panel

    profesor = user.perfil_profesor
    bloqueos = _bloqueos_comunes(user, ticket)
    por_dictar = Inscripcion.objects.filter(clase__profesor=profesor, estado__in=Inscripcion.ESTADOS_ACTIVOS,
                                            sesion__fecha_hora_inicio__gt=timezone.now()).count()
    if por_dictar:
        bloqueos.append(f'Tiene {por_dictar} clase(s) reservada(s) por dictar: hay que dictarlas o cancelarlas antes.')
    sin_usar = sum(p.clases_disponibles for p in PaqueteClases.objects.vigentes().filter(profesor=profesor))
    if sin_usar:
        bloqueos.append(f'Hay {sin_usar} clase(s) pagada(s) sin usar por alumnos con este profesor: se perderían.')
    disponible = calcular_saldos(profesor)['disponible']
    if disponible:
        bloqueos.append(f'Tiene {formato_clp(disponible)} disponibles para retirar: hay que retirarlos antes.')
    en_tramite = profesor.retiros.filter(estado__in=(SolicitudRetiro.PENDIENTE, SolicitudRetiro.APROBADO)).count()
    if en_tramite:
        bloqueos.append(f'Tiene {en_tramite} retiro(s) de dinero en trámite: hay que terminarlos antes.')
    propias = [DATOS_CUENTA,
               Categoria('Título profesional y especializaciones', ELIMINA,
                         'Los documentos de tu título y tus especializaciones, y las observaciones de su revisión.'),
               Categoria('Cuenta bancaria y horario', ELIMINA,
                         'La cuenta donde se te paga y tu horario. Dejas de aparecer en el catálogo y se cancelan '
                         'las clases programadas que no tengan reservas.')]
    return Evaluacion(_categorias(user, propias, 'alumnos', HISTORIAL_PROFESOR), tuple(bloqueos))


def _apoderado(user, ticket):
    bloqueos = _bloqueos_comunes(user, ticket)
    vigentes = [v for v in user.perfil_apoderado.vinculos.filter(estado=Vinculo.VERIFICADO).select_related('alumno__user')
                if es_menor(v.alumno.user)]
    if vigentes:
        bloqueos.append(f'Es el apoderado verificado de {len(vigentes)} estudiante(s) menor(es): hay que desvincularse '
                        'de cada uno antes, o quedarían sin apoderado.')
    propias = [DATOS_CUENTA,
               Categoria('Documentos de identidad', ELIMINA,
                         'Tu carnet y los certificados que hayan quedado guardados, y tu correo en las invitaciones.')]
    return Evaluacion(_categorias(user, propias, 'profesores', HISTORIAL_APODERADO), tuple(bloqueos))


EVALUADORES = {ALUMNO.clave: _alumno, PROFESOR.clave: _profesor, APODERADO.clave: _apoderado}


def evaluar(user, ticket=None):
    """Que pasaria hoy con la cuenta de ``user``. ``ticket``: el de su solicitud (no cuenta como gestion abierta)."""
    rol, _ = resolver_rol(user)
    evaluador = EVALUADORES.get(rol.clave) if rol else None
    if evaluador is None:
        etiqueta = rol.etiqueta.lower() if rol else 'esta cuenta'
        return Evaluacion((), (f'Una cuenta de {etiqueta} no se elimina desde aquí: hay que tratarla con el equipo.',))
    return evaluador(user, ticket)
