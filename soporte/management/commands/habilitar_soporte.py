"""python manage.py habilitar_soporte RUT [--agregar contacto otro] [--quitar tecnico]

Cambia los temas (categorias de tickets) de un agente de soporte que ya existe. Los
temas se eligen al crearlo (crear_soporte); este comando los agrega o quita despues,
por ejemplo para que alguien atienda una categoria nueva como Contacto.

Quitar un tema no cambia los tickets que el agente ya tiene: dejan de aparecerle y el
lider los ve como tickets sin agente que los atienda, para reasignarlos.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from alumnos.backends import variaciones_rut
from alumnos.management.commands.crear_admin import normalizar_rut
from soporte.models import AgenteSoporte, Habilitacion, Ticket

CATEGORIAS = [clave for clave, _ in Ticket.CATEGORIAS]


class Command(BaseCommand):
    help = 'Agrega o quita temas (categorías de tickets) a un agente de soporte.'

    def add_arguments(self, parser):
        parser.add_argument('rut', help='RUT del agente, con o sin puntos.')
        parser.add_argument('--agregar', nargs='+', default=[], choices=CATEGORIAS, help='Temas que empieza a atender.')
        parser.add_argument('--quitar', nargs='+', default=[], choices=CATEGORIAS, help='Temas que deja de atender.')

    def handle(self, *args, rut, agregar, quitar, **opciones):
        if not agregar and not quitar:
            raise CommandError('Indica --agregar o --quitar.')
        if set(agregar) & set(quitar):
            raise CommandError('Un tema no puede estar en --agregar y en --quitar a la vez.')
        agente = self._agente(rut)
        with transaction.atomic():
            Habilitacion.objects.bulk_create([Habilitacion(agente=agente, categoria=c) for c in set(agregar)],
                                             ignore_conflicts=True)  # si ya lo atendia, no pasa nada
            agente.habilitaciones.filter(categoria__in=quitar).delete()
        self._avisar_tickets_que_deja(agente, quitar)
        nombres = dict(Ticket.CATEGORIAS)
        temas = ', '.join(sorted(nombres[c] for c in agente.categorias)) or 'ninguno'
        self.stdout.write(self.style.SUCCESS(f'{agente.nombre} ahora atiende: {temas}.'))

    def _agente(self, rut):
        variantes = variaciones_rut(normalizar_rut(rut))
        agente = (AgenteSoporte.objects.select_related('user')
                  .filter(Q(user__rut__in=variantes) | Q(user__username__in=variantes)).first())
        if agente is None:
            raise CommandError('No hay un agente de soporte con ese RUT. Para crearlo: crear_soporte.')
        return agente

    def _avisar_tickets_que_deja(self, agente, quitar):
        abiertos = agente.tickets.filter(estado=Ticket.ABIERTO, categoria__in=quitar).count()
        if abiertos:
            self.stdout.write(self.style.WARNING(
                f'Tiene {abiertos} ticket(s) abierto(s) de esos temas: el líder debe reasignarlos.'))
