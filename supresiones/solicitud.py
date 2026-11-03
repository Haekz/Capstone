"""Abrir, ejecutar y rechazar una solicitud de eliminar la cuenta (respuesta legal, E3 pasos 1, 4 y 5).

- ``abrir``: constancia. Crea la solicitud y su ticket de Privacidad y manda el correo de recepcion.
- ``ejecutar``: elimina y restringe con la misma regla de ``mensajes.supresion`` y avisa el resultado. Solo si la
  evaluacion no tiene bloqueos.
- ``rechazar``: soporte explica por que no se puede (o aun no) y cierra el ticket; el usuario lo lee en LBWUS.

Unico lugar que cambia el estado de una solicitud.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from alumnos.roles import resolver_rol
from mensajes.supresion import suprimir_cuenta
from soporte.models import Ticket
from soporte.tickets import abrir_reporte, agregar_mensaje, resolver

from . import correo
from .evaluacion import evaluar
from .models import SolicitudSupresion

TITULO = 'Eliminar mi cuenta'
DESCRIPCION = ('Pedí eliminar mi cuenta y mis datos personales. Confirmé que soy yo con el enlace enviado a mi '
               'correo registrado.')


class SolicitudError(Exception):
    """No se pudo resolver la solicitud; el mensaje se le muestra al agente."""


def _cerrar_obsoletas(user):
    """Una solicitud abierta cuyo ticket se cerro por la via normal (una respuesta con 'cerrar') ya no se va a
    ejecutar. Se da por cerrada, para que el usuario pueda volver a pedirla."""
    SolicitudSupresion.objects.filter(usuario=user, estado=SolicitudSupresion.ABIERTA).exclude(
        ticket__estado=Ticket.ABIERTO).update(
        estado=SolicitudSupresion.RECHAZADA, resuelta=timezone.now(),
        motivo_rechazo='El ticket se cerró sin ejecutar la eliminación.')


def abierta_de(user):
    """La solicitud vigente del usuario, o None."""
    _cerrar_obsoletas(user)
    return SolicitudSupresion.objects.filter(usuario=user, estado=SolicitudSupresion.ABIERTA).first()


def abrir(user):
    """Registra la solicitud ya confirmada por correo. Devuelve (solicitud, creada): si ya habia una abierta,
    esa misma y False."""
    existente = abierta_de(user)
    if existente:
        return existente, False
    rol, _ = resolver_rol(user)
    try:
        with transaction.atomic():
            ticket = abrir_reporte(user, Ticket.PRIVACIDAD, TITULO, DESCRIPCION)
            solicitud = SolicitudSupresion.objects.create(usuario=user, rol=rol.clave, ticket=ticket)
            transaction.on_commit(lambda: correo.constancia(solicitud))
    except IntegrityError:  # dos confirmaciones a la vez: gana la primera
        return abierta_de(user), False
    return solicitud, True


def _bloquear_abierta(pk):
    solicitud = SolicitudSupresion.objects.select_for_update().get(pk=pk)
    if solicitud.estado != SolicitudSupresion.ABIERTA or solicitud.usuario_id is None:
        raise SolicitudError('Esta solicitud ya se resolvió.')
    return solicitud


def ejecutar(solicitud, agente):
    """Elimina la cuenta. Devuelve (borrada, avisada): si se borro completa o se seudonimizo, y si el correo
    del resultado salio."""
    with transaction.atomic():
        solicitud = _bloquear_abierta(solicitud.pk)
        user, ticket = solicitud.usuario, solicitud.ticket
        evaluacion = evaluar(user, ticket)
        if not evaluacion.puede:
            raise SolicitudError('Hoy no se puede eliminar: ' + ' '.join(evaluacion.bloqueos))
        nombre, destino = user.first_name, user.email  # despues de eliminar ya no existen
        resolver(ticket)
        borrada = suprimir_cuenta(user)
        SolicitudSupresion.objects.filter(pk=solicitud.pk).update(
            estado=SolicitudSupresion.EJECUTADA, resuelta=timezone.now(), resuelta_por=agente,
            resultado=SolicitudSupresion.BORRADA if borrada else SolicitudSupresion.SEUDONIMIZADA)
    return borrada, correo.resultado(nombre, destino, solicitud.pk, evaluacion, borrada)


def rechazar(solicitud, agente, motivo):
    """Soporte explica por que no se elimina la cuenta; queda en el ticket, que se cierra."""
    motivo = (motivo or '').strip()
    if not motivo:
        raise SolicitudError('Explica por qué no se puede eliminar la cuenta.')
    with transaction.atomic():
        solicitud = _bloquear_abierta(solicitud.pk)
        agregar_mensaje(solicitud.ticket, agente.user, motivo, de_soporte=True, cerrar=True)
        SolicitudSupresion.objects.filter(pk=solicitud.pk).update(
            estado=SolicitudSupresion.RECHAZADA, resuelta=timezone.now(), resuelta_por=agente, motivo_rechazo=motivo)
