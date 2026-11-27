"""Tarea diaria (dentro de tareas_diarias): borra los videos con 30 dias sin actividad, avisando 7 dias antes.

La logica esta en user_profesor/limpieza_videos.py. Escribe solo cantidades: nunca titulos ni nombres.
Sin R2 configurado los videos estan desactivados y no hay nada que revisar: termina bien, para no alertar todos los
dias. Si la base de datos falla, falla, y tareas_diarias avisa por correo.
"""

from django.core.management.base import BaseCommand

from user_profesor import limpieza_videos
from user_profesor.almacen_videos import AlmacenNoConfigurado


class Command(BaseCommand):
    help = (f'Borra los videos con {limpieza_videos.DIAS_SIN_ACTIVIDAD} dias sin actividad, avisando '
            f'{limpieza_videos.DIAS_AVISO} dias antes.')

    def handle(self, *args, **options):
        try:
            avisados, borrados = limpieza_videos.revisar()
        except AlmacenNoConfigurado:
            self.stdout.write('Videos desactivados (sin R2): nada que revisar.')
            return
        self.stdout.write(f'Avisados: {avisados}. Borrados: {borrados}.')
