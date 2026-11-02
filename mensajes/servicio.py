"""Quien puede escribir, el envio y los avisos (paso C1a, decidido 02-nov).

- Solo con una reserva activa o un paquete vigente entre alumno y profesor (se revisa en cada envio).
- Un menor nunca escribe ni abre conversaciones: hablara su apoderado (C2).
- Aviso al otro lado (campanita + correo sin el contenido) solo cuando cambia el turno:
  si alguien manda varios seguidos, no se llena de avisos.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from alumnos.correo import enviar as enviar_correo
from alumnos.models import Inscripcion, PaqueteClases
from alumnos.utils import es_menor
from notificaciones.models import notificar

from .filtro import exigir_sin_contacto
from .models import LARGO_MAX, Conversacion, Mensaje

PLANTILLA_CORREO = 'mensajes/correo_nuevo_mensaje.txt'


class MensajeError(ValidationError):
    pass


def _tiene_relacion(alumno, profesor):
    reserva = Inscripcion.objects.filter(alumno=alumno, clase__profesor=profesor,
                                         estado__in=Inscripcion.ESTADOS_ACTIVOS).exists()
    return reserva or PaqueteClases.objects.vigentes().filter(alumno=alumno, profesor=profesor).exists()


def _exigir_relacion(alumno, profesor):
    if not _tiene_relacion(alumno, profesor):
        raise MensajeError('Solo pueden escribirse quienes tienen una clase reservada o un paquete activo.')


def abrir_conversacion(alumno, profesor):
    """La conversacion del alumno adulto con el profesor (se crea la primera vez)."""
    if es_menor(alumno.user):
        raise MensajeError('Los menores no tienen mensajes: escribe su apoderado.')
    _exigir_relacion(alumno, profesor)
    conversacion, _ = Conversacion.objects.get_or_create(alumno=alumno, profesor=profesor, cliente=alumno.user)
    return conversacion


def marcar_visto(user, conversacion):
    """`user` leyo la conversacion hasta ahora: lo anterior de la otra persona ya no esta sin leer."""
    campo = 'visto_cliente' if user.pk == conversacion.cliente_id else 'visto_profesor'
    Conversacion.objects.filter(pk=conversacion.pk).update(**{campo: timezone.now()})


def _avisar(conversacion, autor):
    habla_el_cliente = autor.pk == conversacion.cliente_id
    destinatario = conversacion.profesor.user if habla_el_cliente else conversacion.cliente
    enlace = f"{reverse('panel_profesor')}?c={conversacion.pk}" if habla_el_cliente else ''  # el del alumno: C1b-2
    notificar(destinatario, f'{autor.first_name} te escribió un mensaje.', enlace)
    enviar_correo('Tienes un mensaje nuevo', PLANTILLA_CORREO, {'nombre': destinatario.first_name}, destinatario.email)


def enviar(autor, conversacion, texto):
    """Guarda el mensaje si quien escribe participa, puede escribir y no comparte un contacto."""
    texto = (texto or '').strip()
    if not texto:
        raise MensajeError('Escribe un mensaje.')
    if len(texto) > LARGO_MAX:
        raise MensajeError(f'El mensaje puede tener hasta {LARGO_MAX} caracteres.')
    if es_menor(autor) or not conversacion.es_participante(autor):
        raise MensajeError('No puedes escribir en esta conversación.')
    _exigir_relacion(conversacion.alumno, conversacion.profesor)
    exigir_sin_contacto(texto)
    with transaction.atomic():
        anterior = conversacion.mensajes.last()
        mensaje = Mensaje.objects.create(conversacion=conversacion, autor=autor, texto=texto)
        if anterior is None or anterior.autor_id != autor.pk:
            transaction.on_commit(lambda: _avisar(conversacion, autor))
    return mensaje
