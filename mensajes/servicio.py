"""Quien puede escribir, el envio y los avisos (paso C1a, decidido 02-nov).

- Solo con una reserva activa o un paquete vigente entre alumno y profesor (se revisa en cada envio).
- Un menor nunca escribe ni abre conversaciones: habla su apoderado (C2), con su propia conversacion por
  cada apoderado. Si el vinculo se revoca, el apoderado se rechaza o el estudiante cumple 18 (Vinculo.autoriza),
  la conversacion queda solo para lectura, para los dos lados.
- Aviso al otro lado (campanita + correo sin el contenido) solo cuando cambia el turno:
  si alguien manda varios seguidos, no se llena de avisos.
- Reportar (C1c): cualquiera de los dos abre un ticket de soporte; solo soporte puede leerla desde el
  ticket y cada lectura queda registrada.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from alumnos.correo import enviar as enviar_correo
from alumnos.models import Inscripcion, PaqueteClases
from alumnos.utils import es_menor
from apoderados.models import Vinculo
from notificaciones.models import notificar
from soporte.models import Ticket
from soporte.tickets import abrir_reporte

from .filtro import exigir_sin_contacto
from .models import LARGO_MAX, AccesoConversacion, Conversacion, Mensaje, ReporteConversacion

PLANTILLA_CORREO = 'mensajes/correo_nuevo_mensaje.txt'


class MensajeError(ValidationError):
    pass


def ids_profesores_con_relacion(alumno):
    """Profesores con quienes el alumno tiene una reserva activa o un paquete vigente."""
    con_reserva = Inscripcion.objects.filter(alumno=alumno, estado__in=Inscripcion.ESTADOS_ACTIVOS)
    con_paquete = PaqueteClases.objects.vigentes().filter(alumno=alumno)
    ids = set(con_reserva.values_list('clase__profesor_id', flat=True))
    ids.update(con_paquete.values_list('profesor_id', flat=True))
    ids.discard(None)  # paquete cuyo profesor ya no existe
    return ids


def _exigir_relacion(alumno, profesor):
    if profesor.pk not in ids_profesores_con_relacion(alumno):
        raise MensajeError('Solo pueden escribirse quienes tienen una clase reservada o un paquete activo.')


def abrir_conversacion_de_apoderado(vinculo, profesor):
    """La conversacion de este apoderado con el profesor, en representacion del menor."""
    if not vinculo.autoriza(vinculo.alumno):
        raise MensajeError('Este vínculo ya no está activo.')
    _exigir_relacion(vinculo.alumno, profesor)
    conversacion, _ = Conversacion.objects.get_or_create(alumno=vinculo.alumno, profesor=profesor,
                                                         cliente=vinculo.apoderado.user)
    return conversacion


def abrir_conversaciones_con_apoderados(alumno, profesor):
    """El profesor escribe por un menor: una conversacion con cada apoderado con vinculo vigente (se crean
    la primera vez). Vacio si el menor no tiene ninguno."""
    vinculos = (Vinculo.objects.filter(alumno=alumno, estado=Vinculo.VERIFICADO)
                .select_related('apoderado__user', 'alumno__user'))
    return [abrir_conversacion_de_apoderado(v, profesor) for v in vinculos if v.autoriza(alumno)]


def es_solo_lectura(conversacion):
    """La de un apoderado cuyo vinculo ya no autoriza actuar por el estudiante (revocado, apoderado
    rechazado o estudiante de 18 años). Las de un alumno adulto siempre se pueden usar."""
    if not conversacion.es_de_apoderado:
        return False
    vinculo = Vinculo.objects.filter(apoderado__user_id=conversacion.cliente_id, alumno=conversacion.alumno).first()
    return vinculo is None or not vinculo.autoriza(conversacion.alumno)


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


def _aviso_a_quien_no_escribio(conversacion, autor):
    """(destinatario, texto, enlace). Al profesor le llega "Apoderado de <menor>", nunca el nombre del
    apoderado; al apoderado, de que estudiante se trata."""
    if autor.pk == conversacion.cliente_id:
        return (conversacion.profesor.user, f'{conversacion.nombre_para_profesor} te escribió un mensaje.',
                reverse('panel_profesor'))
    sobre = f' sobre {conversacion.alumno.user.first_name}' if conversacion.es_de_apoderado else ''
    ruta = 'mensajes_apoderado' if conversacion.es_de_apoderado else 'alumno_pag1'
    return conversacion.cliente, f'{autor.first_name} te escribió un mensaje{sobre}.', reverse(ruta)


def _avisar(conversacion, autor):
    destinatario, texto, ruta = _aviso_a_quien_no_escribio(conversacion, autor)
    notificar(destinatario, texto, f'{ruta}?c={conversacion.pk}')
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
    if es_solo_lectura(conversacion):
        raise MensajeError('Esta conversación quedó solo para lectura: el vínculo con el estudiante ya no está activo.')
    _exigir_relacion(conversacion.alumno, conversacion.profesor)
    exigir_sin_contacto(texto)
    with transaction.atomic():
        anterior = conversacion.mensajes.last()
        mensaje = Mensaje.objects.create(conversacion=conversacion, autor=autor, texto=texto)
        if anterior is None or anterior.autor_id != autor.pk:
            transaction.on_commit(lambda: _avisar(conversacion, autor))
    return mensaje


def reportar(usuario, conversacion, descripcion):
    """Un participante reporta la conversacion: abre un ticket de Conducta (aviso inmediato a los
    lideres, plazo de 2 dias habiles). Quien reporta cuenta con sus propias palabras; el texto de la
    conversacion no se copia al ticket. Uno abierto por persona: no se llena soporte con repetidos."""
    if not conversacion.es_participante(usuario):
        raise MensajeError('No puedes reportar esta conversación.')
    with transaction.atomic():
        ya = ReporteConversacion.objects.filter(conversacion=conversacion, reportado_por=usuario,
                                                ticket__estado=Ticket.ABIERTO)
        if ya.exists():
            raise MensajeError('Ya reportaste esta conversación: soporte la está revisando.')
        estudiante = conversacion.alumno if usuario.pk == conversacion.cliente_id and conversacion.es_de_apoderado else None
        ticket = abrir_reporte(usuario, Ticket.CONDUCTA, f'Conversación #{conversacion.pk} reportada', descripcion,
                               estudiante=estudiante)  # D18: el apoderado reporta por su estudiante
        return ReporteConversacion.objects.create(conversacion=conversacion, ticket=ticket, reportado_por=usuario)


def leer_reportada(reporte, agente):
    """Soporte abre la conversacion reportada: queda registrado quien y cuando. Devuelve sus mensajes."""
    AccesoConversacion.objects.create(reporte=reporte, agente=agente)
    return list(reporte.conversacion.mensajes.select_related('autor'))
