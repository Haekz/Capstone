"""Tarea diaria (dentro de tareas_diarias): borra los videos con 30 dias sin actividad, avisando 7 dias antes.

La logica esta en user_profesor/limpieza_videos.py. Escribe solo cantidades: nunca titulos ni nombres.
Sin MongoDB (donde estan las fichas) no hay videos que revisar: termina bien, para no alertar todos los dias. Si esta
configurado pero no responde, falla, y tareas_diarias avisa por correo.
"""

from django.core.management.base import BaseCommand

from comunidad.mongo import MongoNoConfigurado
from user_profesor import limpieza_videos


class Command(BaseCommand):
    help = (f'Borra los videos con {limpieza_videos.DIAS_SIN_ACTIVIDAD} dias sin actividad, avisando '
            f'{limpieza_videos.DIAS_AVISO} dias antes.')

    def handle(self, *args, **options):
        try:
            avisados, borrados = limpieza_videos.revisar()
        except MongoNoConfigurado:
            self.stdout.write('Videos desactivados (sin MongoDB): nada que revisar.')
            return
        self.stdout.write(f'Avisados: {avisados}. Borrados: {borrados}.')
