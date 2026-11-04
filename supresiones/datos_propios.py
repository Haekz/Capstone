"""Datos propios de cada rol al eliminar una cuenta (respuesta legal del 02-nov, E5 / paso 5).

``mensajes.supresion.suprimir_cuenta`` decide *si* se borra la cuenta o se seudonimiza; este modulo le dice dos
cosas que dependen del rol:

- ``tiene_historial``: hay registros de otras personas o de la contabilidad que dependen de la cuenta, asi que la
  fila se conserva (seudonimizada) en vez de borrarla. Borrar un profesor arrastraria sus clases, sesiones e
  inscripciones: el historial de otros alumnos.
    * alumno: paquetes, suscripciones o clases;
    * profesor: clases con inscripciones, paquetes vendidos o retiros de dinero;
    * apoderado: compras pagadas o un vinculo que llego a estar verificado (quien tuvo autoridad sobre un menor).
- ``limpiar``: los datos propios que se quitan siempre, se borre la cuenta o se seudonimice (la cascada no borra los
  archivos del disco ni los correos que otras filas copiaron): foto, y por rol observaciones recibidas, titulo,
  cuenta bancaria, carnet.

Para todos los roles: las filas de allauth (correo y datos de Google) se borran; sin eso el correo seguiria guardado.
"""

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.db.models import Q
from django.utils import timezone

from agenda.models import HorarioSemanal
from alumnos.models import CuentaBancaria, Inscripcion, PaqueteClases, Profesor, SesionClase
from apoderados.models import Documento, Invitacion, SolicitudAdolescente, Vinculo
from observaciones.models import Observacion


def _perfil(user, nombre):
    return getattr(user, nombre, None)  # el perfil que no existe es AttributeError: da None


def _alumno_con_historial(alumno):
    return alumno.paquetes.exists() or alumno.suscripciones.exists() or Inscripcion.objects.filter(alumno=alumno).exists()


def _profesor_con_historial(profesor):
    return (Inscripcion.objects.filter(clase__profesor=profesor).exists()
            or PaqueteClases.objects.filter(profesor=profesor).exists() or profesor.retiros.exists())


def _apoderado_con_historial(apoderado):
    return (apoderado.compras.exists()
            or apoderado.vinculos.exclude(estado__in=(Vinculo.PENDIENTE, Vinculo.RECHAZADO)).exists())


_HISTORIAL = (('perfil_alumno', _alumno_con_historial), ('perfil_profesor', _profesor_con_historial),
              ('perfil_apoderado', _apoderado_con_historial))


def tiene_historial(user):
    for nombre, con_historial in _HISTORIAL:
        perfil = _perfil(user, nombre)
        if perfil is not None and con_historial(perfil):
            return True
    return False


def _limpiar_alumno(alumno):
    """Sin las observaciones que recibio: son un juicio sobre la persona y sin ella no sirven de nada."""
    Observacion.objects.filter(inscripcion__alumno=alumno).delete()


def _limpiar_profesor(profesor):
    """Sin titulo, cuenta bancaria ni horario, y fuera del catalogo: sin titulo aprobado no se hacen clases."""
    if profesor.titulo_archivo:
        profesor.titulo_archivo.delete(save=False)  # el archivo del titulo, no solo la referencia
    profesor.titulo_contenido, profesor.titulo_formato, profesor.titulo_observacion = None, '', ''
    profesor.titulo_estado, profesor.titulo_actualizado = Profesor.TITULO_PENDIENTE, None
    profesor.save()
    CuentaBancaria.objects.filter(profesor=profesor).delete()
    HorarioSemanal.objects.filter(profesor=profesor).delete()
    SesionClase.objects.filter(clase__profesor=profesor, estado='programada', fecha_hora_inicio__gt=timezone.now()
                               ).update(estado='cancelada')  # sin clases reservadas (lo exige la evaluacion)


def _limpiar_apoderado(apoderado):
    """Sin carnet ni certificados, y sin su correo en las invitaciones que guardan los estudiantes."""
    Documento.objects.filter(Q(apoderado=apoderado) | Q(vinculo__apoderado=apoderado)).delete()
    Invitacion.objects.filter(vinculo__apoderado=apoderado).update(correo='')
    SolicitudAdolescente.objects.filter(invitaciones__vinculo__apoderado=apoderado).update(correo_apoderado='')


def limpiar(user):
    if user.foto_perfil:
        user.foto_perfil.delete(save=False)  # tambien el archivo, no solo la referencia
    EmailAddress.objects.filter(user=user).delete()
    SocialAccount.objects.filter(user=user).delete()
    alumno = _perfil(user, 'perfil_alumno')
    if alumno is not None:
        _limpiar_alumno(alumno)
    profesor = _perfil(user, 'perfil_profesor')
    if profesor is not None:
        _limpiar_profesor(profesor)
    apoderado = _perfil(user, 'perfil_apoderado')
    if apoderado is not None:
        _limpiar_apoderado(apoderado)
