"""Abrir, cerrar, reasignar y escalar tickets. Unico lugar que cambia su estado o su agente.

Los correos salen al confirmar la transaccion: nunca avisan de un ticket que se deshizo.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from .correo import (avisar_asignacion, avisar_conducta, avisar_contestacion, avisar_escalamiento_admin,
                     avisar_indicacion, avisar_respuesta, avisar_sin_asignar, lideres)
from .models import AgenteSoporte, Asignacion, Escalamiento, Mensaje, Ticket
from .plazos import vencimiento


def agentes_habilitados(categoria):
    """Agentes con cuenta activa que reciben tickets de ``categoria``."""
    return AgenteSoporte.objects.filter(user__is_active=True, habilitaciones__categoria=categoria)


def _con_menos_carga(agentes):
    """De ``agentes``, el con menos tickets abiertos; empate: el mas antiguo. None si no hay."""
    return (agentes.annotate(abiertos=Count('tickets', filter=Q(tickets__estado=Ticket.ABIERTO)))
            .order_by('abiertos', 'id_agente').first())


def _agente_con_menos_carga(categoria):
    return _con_menos_carga(agentes_habilitados(categoria))


def abrir_ticket(categoria, **revisado):
    """Abre el ticket de ``revisado`` (apoderado=, vinculo= o profesor=) si no tiene
    uno abierto en esa categoria, con su plazo, y lo asigna solo. Sin agente habilitado
    queda sin asignar y se avisa a los lideres."""
    with transaction.atomic():
        if Ticket.objects.filter(estado=Ticket.ABIERTO, categoria=categoria, **revisado).exists():
            return
        _crear(categoria, **revisado)


def abrir_reporte(autor, categoria, titulo, descripcion, estudiante=None):
    """Ticket que abre un usuario (D10). Puede tener varios abiertos a la vez.
    ``estudiante``: si lo abre un apoderado por uno de sus estudiantes."""
    with transaction.atomic():
        return _crear(categoria, autor=autor, titulo=titulo, descripcion=descripcion, estudiante=estudiante)


def abrir_contacto(mensaje):
    """Guarda el ``MensajeContacto`` (sin guardar) del formulario publico y abre su ticket (H14):
    los dos o ninguno."""
    with transaction.atomic():
        mensaje.save()
        return _crear(Ticket.CONTACTO, contacto=mensaje)


def _crear(categoria, **campos):
    """Crea el ticket con su plazo y lo asigna al agente con menos carga. Conducta:
    los lideres se enteran siempre (N5), y ese aviso ya dice si quedo sin asignar."""
    agente = _agente_con_menos_carga(categoria)
    ticket = Ticket.objects.create(categoria=categoria, asignado=agente,
                                   vence=vencimiento(timezone.now(), Ticket.DIAS_HABILES[categoria]),
                                   **campos)
    if categoria == Ticket.CONDUCTA:
        transaction.on_commit(lambda: avisar_conducta(ticket))
    elif agente is None:
        transaction.on_commit(lambda: avisar_sin_asignar(ticket))
    if agente is not None:
        Asignacion.objects.create(ticket=ticket, agente=agente)
        transaction.on_commit(lambda: avisar_asignacion(ticket))
    return ticket


def cerrar_tickets(tickets):
    """Cierra los tickets abiertos de un related manager (``revisado.tickets``)."""
    tickets.filter(estado=Ticket.ABIERTO).update(estado=Ticket.CERRADO, cerrado=timezone.now())


def resolver(ticket):
    """Cierra el ticket porque una accion de soporte lo resolvio (no un mensaje); cumple el plazo."""
    Ticket.objects.filter(pk=ticket.pk, respondido__isnull=True).update(respondido=timezone.now())
    cerrar_tickets(Ticket.objects.filter(pk=ticket.pk))


def _exigir_abierto(ticket):
    if ticket.estado != Ticket.ABIERTO:
        raise ValidationError('Ese ticket ya está cerrado.')


def cerrar_sin_respuesta(ticket):
    """Contacto que no necesita respuesta (spam, repetido): se cierra sin correo y cumple el plazo."""
    _exigir_abierto(ticket)
    resolver(ticket)


def agregar_mensaje(ticket, autor, texto, de_soporte, cerrar=False):
    """Respuesta en un ticket de usuario abierto. Soporte puede cerrarlo con ella, y su
    primera respuesta cumple el plazo. Avisa a la otra parte; al visitante de Contactanos,
    con el texto, porque no tiene donde leerlo (soporte/correo.avisar_respuesta)."""
    _exigir_abierto(ticket)
    with transaction.atomic():
        Mensaje.objects.create(ticket=ticket, autor=autor, texto=texto, de_soporte=de_soporte)
        if de_soporte:
            Ticket.objects.filter(pk=ticket.pk, respondido__isnull=True).update(respondido=timezone.now())
        if cerrar:
            cerrar_tickets(Ticket.objects.filter(pk=ticket.pk))
        ticket.refresh_from_db()
        if de_soporte:
            transaction.on_commit(lambda: avisar_respuesta(ticket, texto))
        elif ticket.asignado_id:
            transaction.on_commit(lambda: avisar_contestacion(ticket))


def reasignar(ticket, agente, autor):
    """El lider pasa un ticket abierto a otro agente habilitado en su categoria.
    El plazo no cambia."""
    _exigir_abierto(ticket)
    if not agentes_habilitados(ticket.categoria).filter(pk=agente.pk).exists():
        raise ValidationError('Ese agente no atiende tickets de esta categoría.')
    with transaction.atomic():
        ticket.asignado = agente
        ticket.save(update_fields=['asignado'])
        Asignacion.objects.create(ticket=ticket, agente=agente, autor=autor)
        transaction.on_commit(lambda: avisar_asignacion(ticket))


def escalar(ticket, agente, motivo, asignatura_pedida=''):
    """Caso grave: un agente lo pasa al lider con menos carga, que lo toma como suyo (aunque no
    atienda la categoria); un lider lo lleva a los administradores, y el ticket sigue en soporte.
    El plazo no cambia. Devuelve el Escalamiento.

    ``asignatura_pedida`` (fase 4): el lider le pide al admin crear esa asignatura; el agente no puede."""
    _exigir_abierto(ticket)
    if asignatura_pedida and not agente.es_lider:
        raise ValidationError('Solo el líder de soporte puede pedirle una asignatura al administrador.')
    if agente.es_lider:
        return _escalar_al_admin(ticket, agente.user, motivo, asignatura_pedida)
    lider = _con_menos_carga(lideres())
    if lider is None:
        raise ValidationError('No hay un líder de soporte activo a quien escalarlo.')
    with transaction.atomic():
        escalamiento = Escalamiento.objects.create(ticket=ticket, destino=Escalamiento.AL_LIDER,
                                                   autor=agente.user, motivo=motivo)
        ticket.asignado = lider
        ticket.save(update_fields=['asignado'])
        Asignacion.objects.create(ticket=ticket, agente=lider, autor=agente.user)
        transaction.on_commit(lambda: avisar_asignacion(ticket, escalado=True))
    return escalamiento


def _escalar_al_admin(ticket, autor, motivo, asignatura_pedida=''):
    try:
        with transaction.atomic():
            escalamiento = Escalamiento.objects.create(ticket=ticket, destino=Escalamiento.AL_ADMIN, autor=autor,
                                                       motivo=motivo, asignatura_pedida=asignatura_pedida)
    except IntegrityError:  # un_escalamiento_al_admin_pendiente
        raise ValidationError('Ese ticket ya está escalado: espera la indicación del administrador.')
    transaction.on_commit(lambda: avisar_escalamiento_admin(escalamiento))
    return escalamiento


def indicar(escalamiento, admin, indicacion):
    """El administrador responde un caso que le escalaron; soporte la ejecuta."""
    with transaction.atomic():
        actualizados = (Escalamiento.objects
                        .filter(pk=escalamiento.pk, destino=Escalamiento.AL_ADMIN, indicado__isnull=True)
                        .update(indicacion=indicacion, indicado_por=admin, indicado=timezone.now()))
        if not actualizados:  # otro admin respondio primero
            raise ValidationError('Ese caso ya tiene una indicación.')
        escalamiento.refresh_from_db()
        transaction.on_commit(lambda: avisar_indicacion(escalamiento))
