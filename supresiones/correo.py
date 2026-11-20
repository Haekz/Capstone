"""Correos del flujo de eliminar la cuenta: enlace de confirmacion, constancia y resultado.

Devuelven False si el correo no salio (alumnos.correo.enviar). El del resultado se manda a los datos copiados
ANTES de eliminar la cuenta, porque despues el correo ya no existe.
"""

from django.utils import timezone

from alumnos.correo import enviar


def enlace_de_confirmacion(user, enlace, horas):
    return enviar('Confirma que quieres eliminar tu cuenta', 'supresiones/correo_enlace.txt',
                  {'nombre': user.first_name, 'enlace': enlace, 'horas': horas}, user.email)


def constancia(solicitud):
    """Constancia de recepcion: numero, fecha y plazo de respuesta. Sin mas datos del usuario."""
    usuario, ticket = solicitud.usuario, solicitud.ticket
    return enviar(f'Recibimos tu solicitud #{solicitud.pk}', 'supresiones/correo_constancia.txt',
                  {'nombre': usuario.first_name, 'solicitud': solicitud, 'ticket': ticket,
                   'recibida': timezone.localtime(solicitud.creada), 'plazo': timezone.localtime(ticket.vence)},
                  usuario.email)


def resultado(nombre, correo_destino, solicitud_pk, evaluacion, borrada):
    """Resultado de la eliminacion: que se elimino y que se conserva, por categoria."""
    if not correo_destino:
        return False
    return enviar(f'Eliminamos tu cuenta (solicitud #{solicitud_pk})', 'supresiones/correo_resultado.txt',
                  {'nombre': nombre, 'solicitud_pk': solicitud_pk, 'evaluacion': evaluacion, 'borrada': borrada,
                   'ahora': timezone.localtime()}, correo_destino)
