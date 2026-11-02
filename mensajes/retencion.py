"""Borrado de conversaciones sin actividad (paso C1d, decidido 02-nov).

Finalidad de los mensajes: coordinar las clases. Pasados 90 dias sin actividad dejan de ser necesarios.

- Inactividad = dias desde el ultimo mensaje (sin mensajes, desde que se creo). Decidido 02-nov tras la
  respuesta legal: una clase ya dictada no extiende la conservacion; una clase futura reservada si impide borrar.
- No se borra si hay un paquete vigente entre las partes, un ticket abierto de cualquiera de ellas
  (puede demorar el borrado unos dias, hasta que soporte lo cierre), ni si esta retenida por un reporte
  (mensajes/revision.py): con ticket abierto, esperando la decision del lider o conservada. Una que el lider
  libera vuelve a esta regla (C1f).
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from alumnos.models import Inscripcion, PaqueteClases
from soporte.models import Ticket

from .models import Conversacion, Mensaje
from .revision import retenidas

DIAS_SIN_ACTIVIDAD = 90


def candidatas():
    """Conversaciones que ya se pueden borrar."""
    ultimo_mensaje = Mensaje.objects.filter(conversacion=OuterRef('pk')).order_by('-creado').values('creado')[:1]
    clase_futura = Inscripcion.objects.filter(alumno=OuterRef('alumno'), clase__profesor=OuterRef('profesor'),
                                              estado__in=Inscripcion.ESTADOS_ACTIVOS,
                                              sesion__fecha_hora_inicio__gt=timezone.now())
    paquete_vigente = PaqueteClases.objects.vigentes().filter(alumno=OuterRef('alumno'), profesor=OuterRef('profesor'))
    ticket_abierto = Ticket.objects.filter(estado=Ticket.ABIERTO).filter(
        Q(autor=OuterRef('cliente')) | Q(autor=OuterRef('profesor__user_id')))
    retenida = retenidas().values('pk')
    desde = timezone.now() - timedelta(days=DIAS_SIN_ACTIVIDAD)
    return (Conversacion.objects
            .annotate(actividad=Coalesce(Subquery(ultimo_mensaje), F('creada')))
            .filter(actividad__lt=desde)
            .exclude(Exists(clase_futura))
            .exclude(Exists(paquete_vigente)).exclude(Exists(ticket_abierto)).exclude(pk__in=retenida))


def borrar_inactivas():
    """Borra las candidatas (con sus mensajes) y devuelve cuantas fueron."""
    with transaction.atomic():
        ids = list(candidatas().values_list('pk', flat=True))
        Conversacion.objects.filter(pk__in=ids).delete()
    return len(ids)
