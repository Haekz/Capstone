from django import template

from alumnos.models import Clase, Profesor
from soporte.models import Ticket

from ..models import HorarioSemanal
from ..panel import HORAS

register = template.Library()


@register.simple_tag
def horario_del_ticket(ticket):
    """Horario del profesor que abrio un ticket de Horario (fase 7); None si no lo es. Asi el detalle del ticket
    (app soporte) no importa esta app."""
    if ticket.categoria != Ticket.HORARIO:
        return None
    profesor = Profesor.objects.filter(user_id=ticket.autor_id).first()
    if profesor is None:
        return None
    return {
        'franjas': HorarioSemanal.objects.filter(profesor=profesor).select_related('clase__asignatura'),
        'clases': Clase.objects.filter(profesor=profesor).select_related('asignatura'),
        'dias': HorarioSemanal.DIAS,
        'horas': HORAS,
    }
