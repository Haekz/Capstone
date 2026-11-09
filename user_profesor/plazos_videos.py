"""Plazos del agregado de videos (fase 5a): aviso al profesor 3 dias antes de cada fecha limite y ticket a soporte
si se atrasa (docs/POLITICA_PAQUETES.md, seccion 12). Corre a diario: tareas_diarias -> avisar_entregas_videos.

Lo que falta y si esta atrasado lo calcula entregas.estado(), lo mismo que ve el profesor en su panel. El ticket es
uno por profesor con todos sus atrasos y se abre como conversacion a su nombre: soporte lo atiende en su pantalla de
siempre y el profesor puede responder. Mientras siga abierto no se repite. Del alumno, solo el nombre de pila.
"""

from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from alumnos import avisos_profesor
from soporte.models import Ticket
from soporte.tickets import abrir_reporte

from . import entregas

AVISO_ANTES = timedelta(days=3)
TITULO_ATRASO = 'Entrega de videos atrasada'


def revisar(ahora=None):
    """Avisa lo que vence en 3 dias y abre los tickets de atraso. Devuelve (avisos, tickets nuevos)."""
    ahora = ahora or timezone.now()
    hoy = timezone.localdate(ahora)
    avisos, atrasos = 0, defaultdict(list)
    for paquete in entregas.con_agregado().filter(profesor__isnull=False).select_related('profesor__user'):
        limite, falta, atrasada = entregas.estado(paquete, ahora)
        if atrasada:
            atrasos[paquete.profesor].append((paquete, limite, falta))
        elif limite and timezone.localdate(limite) - AVISO_ANTES == hoy:
            avisos_profesor.entrega_proxima(paquete, limite, falta)
            avisos += 1
    return avisos, sum(_abrir_ticket(profesor, filas) for profesor, filas in atrasos.items())


def _abrir_ticket(profesor, filas):
    """1 si abrio el ticket; 0 si ya tenia uno abierto."""
    if Ticket.objects.filter(estado=Ticket.ABIERTO, categoria=Ticket.VIDEOS, autor=profesor.user,
                             titulo=TITULO_ATRASO).exists():
        return 0
    detalle = '\n'.join(f'- {p.alumno.user.first_name} ({p.get_plan_display()}): faltan {falta} desde el '
                        f'{timezone.localtime(limite):%d/%m/%Y}' for p, limite, falta in filas)
    abrir_reporte(profesor.user, Ticket.VIDEOS, TITULO_ATRASO,
                  ('Ticket autom\u00e1tico: hay entregas de videos de apoyo atrasadas.\n'
                   f'{detalle}\n'
                   'Mientras no los comparta, esos videos no se le pagan.')[:2000])
    return 1
