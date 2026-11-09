"""Tarea diaria (dentro de tareas_diarias): plazos del agregado de videos. La logica esta en plazos_videos.py."""

from django.core.management.base import BaseCommand

from user_profesor import plazos_videos


class Command(BaseCommand):
    help = 'Avisa al profesor 3 dias antes de cada entrega de videos y abre un ticket si se atrasa.'

    def handle(self, *args, **options):
        avisos, tickets = plazos_videos.revisar()
        self.stdout.write(f'Avisos: {avisos}. Tickets: {tickets}.')
