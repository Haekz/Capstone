"""Borrado de conversaciones sin actividad (paso C1d, decidido 02-nov).

Finalidad de los mensajes: coordinar las clases. Pasados 90 dias sin actividad dejan de ser necesarios.

- Inactividad = dias desde lo mas reciente entre el ultimo mensaje y la ultima clase entre las partes
  (sin mensajes ni clases, desde que se creo). Una clase futura cuenta como actividad: no se borra.
- No se borra si hay un paquete vigente entre las partes, un ticket abierto de cualquiera de ellas
  (puede demorar el borrado unos dias, hasta que soporte lo cierre), ni si alguien la reporto: una
  conversacion reportada se conserva aunque su ticket ya este cerrado (C1c).
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import DateTimeField, Exists, F, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone

from alumnos.models import Inscripcion, PaqueteClases
from soporte.models import Ticket

from .models import Conversacion, Mensaje

DIAS_SIN_ACTIVIDAD = 90


def candidatas():
    """Conversaciones que ya se pueden borrar."""
    ultimo_mensaje = Mensaje.objects.filter(conversacion=OuterRef('pk')).order_by('-creado').values('creado')[:1]
    ultima_clase = (Inscripcion.objects
                    .filter(alumno=OuterRef('alumno'), clase__profesor=OuterRef('profesor'),
                            estado__in=Inscripcion.ESTADOS_ACTIVOS)
                    .order_by('-sesion__fecha_hora_inicio').values('sesion__fecha_hora_inicio')[:1])
    paquete_vigente = PaqueteClases.objects.vigentes().filter(alumno=OuterRef('alumno'), profesor=OuterRef('profesor'))
    ticket_abierto = Ticket.objects.filter(estado=Ticket.ABIERTO).filter(
        Q(autor=OuterRef('cliente')) | Q(autor=OuterRef('profesor__user_id')))
    reportada = Conversacion.objects.reportadas().values('pk')
    desde = timezone.now() - timedelta(days=DIAS_SIN_ACTIVIDAD)
    return (Conversacion.objects
            .annotate(actividad=Greatest(Coalesce(Subquery(ultimo_mensaje), F('creada')),
                                         Coalesce(Subquery(ultima_clase), F('creada')),
                                         output_field=DateTimeField()))
            .filter(actividad__lt=desde)
            .exclude(Exists(paquete_vigente)).exclude(Exists(ticket_abierto)).exclude(pk__in=reportada))


def borrar_inactivas():
    """Borra las candidatas (con sus mensajes) y devuelve cuantas fueron."""
    with transaction.atomic():
        ids = list(candidatas().values_list('pk', flat=True))
        Conversacion.objects.filter(pk__in=ids).delete()
    return len(ids)
