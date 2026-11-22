"""Aviso al alumno (o a su apoderado) cuando su profesor cancela (paso A3b, decidido 02-nov).

Correo + campanita. Un alumno menor no recibe nada: avisa a sus apoderados con vinculo
verificado. Privacidad: la cancelacion y la clase extra no llevan ningun dato del profesor, solo la asignatura y la
fecha; la reserva (21-nov) lleva ademas su nombre y apellido, sin ningun otro dato.
"""

from django.urls import reverse
from django.utils import timezone

from alumnos.correo_clase import enviar_aviso_clase
from alumnos.utils import es_menor
from apoderados.models import Vinculo
from notificaciones.models import notificar


def _destinatarios(alumno):
    """(usuario, enlace, de_quien) de cada persona a quien avisar."""
    if not es_menor(alumno.user):
        return [(alumno.user, reverse('alumno_pag1'), '')]
    vinculos = Vinculo.objects.filter(alumno=alumno, estado=Vinculo.VERIFICADO).select_related('apoderado__user')
    return [(v.apoderado.user, reverse('apoderado_clases_estudiante', args=[v.pk]),
             f' de {alumno.user.first_name}') for v in vinculos]


def _cuando(momento):
    return timezone.localtime(momento).strftime('%d/%m/%Y a las %H:%M')


def _avisar(alumno, asunto, texto, ruta=None, boton='Ver mis clases'):
    """Campanita y correo a quien corresponda. `texto(de_quien)` dice lo mismo para todos: de_quien es '' para
    el alumno y ' de Ana' para el apoderado de un menor. Con `ruta` el aviso lleva ahi, en vez de a su lista de clases."""
    for user, enlace, de_quien in _destinatarios(alumno):
        mensaje = texto(de_quien)
        notificar(user, mensaje, ruta or enlace)
        enviar_aviso_clase(user, asunto, asunto, [mensaje], boton, ruta or enlace)


def _clase_de(inscripcion):
    """(asignatura, profesional, cuando) como se nombran en los avisos de una clase con sesion."""
    return (inscripcion.clase.asignatura.nombre, inscripcion.clase.profesor.nombre,
            _cuando(inscripcion.sesion.fecha_hora_inicio))


def _sujeto(de_quien):
    return f'La clase{de_quien}' if de_quien else 'Tu clase'


def _autor(vinculo, verbo):
    """' La canceló María.': que los demás apoderados sepan quién fue. Nada si no actuó un apoderado."""
    return f' La {verbo} {vinculo.apoderado.nombre}.' if vinculo else ''


def reserva(inscripcion, vinculo=None):
    """Reserva confirmada (21-nov): avisa al alumno adulto o, si es menor, a sus apoderados verificados, incluido quien
    la hizo. Con el nombre y apellido del profesional y sin ningun otro dato suyo (solo si alumnos/services.py la
    enlaza al confirmarse, on_commit)."""
    asignatura, profesor, cuando = _clase_de(inscripcion)
    autor = _autor(vinculo, 'reservó')

    def texto(de_quien):
        return (f'{_sujeto(de_quien)} ({asignatura}) con {profesor} quedó reservada para el {cuando}.'
                f'{autor if de_quien else ""}')
    _avisar(inscripcion.alumno, 'Clase reservada', texto, reverse('detalle_clase', args=[inscripcion.pk]), 'Ver la clase')


def cancelacion_del_apoderado(inscripcion, vinculo):
    """Un apoderado canceló la clase del menor (21-nov): avisa a todos sus apoderados verificados, incluido quien lo
    hizo. El menor no recibe nada. Con menos de 4 h la clase se descuenta: se dice."""
    asignatura, profesor, cuando = _clase_de(inscripcion)
    autor = _autor(vinculo, 'canceló')
    tarde = (' Faltaban menos de 4 horas: la clase se descontó del paquete.'
             if inscripcion.estado == inscripcion.ESTADO_CANCELADA_TARDE else '')

    def texto(de_quien):
        return f'{_sujeto(de_quien)} ({asignatura}) con {profesor} del {cuando} fue cancelada.{autor if de_quien else ""}{tarde}'
    _avisar(inscripcion.alumno, 'Clase cancelada', texto)


def reagenda_del_apoderado(inscripcion, sesion_anterior, vinculo):
    """Un apoderado movió la clase del menor a otra hora (21-nov): mismos destinatarios que la cancelación."""
    asignatura, profesor, cuando = _clase_de(inscripcion)
    antes = _cuando(sesion_anterior.fecha_hora_inicio)
    autor = _autor(vinculo, 'movió')

    def texto(de_quien):
        return f'{_sujeto(de_quien)} ({asignatura}) con {profesor} pasó del {antes} al {cuando}.{autor if de_quien else ""}'
    _avisar(inscripcion.alumno, 'Clase reagendada', texto, reverse('detalle_clase', args=[inscripcion.pk]), 'Ver la clase')


def recordatorio(inscripcion, plazo):
    """Recordatorio de la clase (21-nov): `plazo` es '24 horas' o '2 horas'. Dice 'en menos de': siempre es cierto,
    aunque el Cron se atrase. Mismos destinatarios y mismo cuidado de datos que la reserva."""
    asignatura, profesor, cuando = _clase_de(inscripcion)

    def texto(de_quien):
        return f'{_sujeto(de_quien)} ({asignatura}) con {profesor} empieza en menos de {plazo}: el {cuando}.'
    _avisar(inscripcion.alumno, f'Recordatorio: tu clase empieza en menos de {plazo}', texto,
            reverse('detalle_clase', args=[inscripcion.pk]), 'Ver la clase')


def cancelacion_del_profesor(inscripcion):
    cuando = _cuando(inscripcion.sesion.fecha_hora_inicio)
    asignatura = inscripcion.clase.asignatura.nombre
    _avisar(inscripcion.alumno, 'Tu profesor canceló una clase', lambda de_quien: (
        f'Tu profesor canceló la clase{de_quien} de {asignatura} del {cuando}. '
        'La clase volvió al paquete: ya puedes reagendarla en otro horario.'))


def _clase_extra(solicitud):
    return solicitud.alumno, solicitud.clase.asignatura.nombre, _cuando(solicitud.fecha_hora_inicio)


def clase_extra_aceptada(solicitud):
    alumno, asignatura, cuando = _clase_extra(solicitud)
    _avisar(alumno, 'Tu clase extra fue aceptada', lambda de_quien: (
        f'Tu profesor aceptó la clase extra{de_quien} de {asignatura} del {cuando}. '
        'Ya está reservada y se descontó una clase del paquete.'))


def clase_extra_rechazada(solicitud):
    alumno, asignatura, cuando = _clase_extra(solicitud)
    deja_mensaje = f' Te dejó este mensaje: {solicitud.motivo_rechazo}' if solicitud.motivo_rechazo else ''
    _avisar(alumno, 'Tu clase extra no fue aceptada', lambda de_quien: (
        f'Tu profesor no pudo aceptar la clase extra{de_quien} de {asignatura} del {cuando}.{deja_mensaje} '
        'Puedes pedir otra hora.'))


def clase_extra_vencida(solicitud, motivo):
    alumno, asignatura, cuando = _clase_extra(solicitud)
    _avisar(alumno, 'Tu pedido de clase extra venció', lambda de_quien: (
        f'Tu pedido de clase extra{de_quien} de {asignatura} del {cuando} venció y no se reservó. {motivo} '
        'Puedes pedir otra hora.'))
