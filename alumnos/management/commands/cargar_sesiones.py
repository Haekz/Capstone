"""python manage.py cargar_sesiones

Crea de 3 a 4 sesiones con distintos horarios y cupos para cada clase disponible en el sistema.
Es idempotente: usa get_or_create y no duplica sesiones para un mismo inicio.
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from alumnos.models import Clase, SesionClase

# Horarios programados relativos a fechas futuras
SESIONES_POR_ASIGNATURA = {
    'Cálculo Diferencial': [
        {'dias': 3, 'hora_inicio': time(9, 30), 'duracion_min': 90, 'cupo': 6, 'precio': Decimal('15000.00')},
        {'dias': 4, 'hora_inicio': time(14, 0), 'duracion_min': 90, 'cupo': 5, 'precio': Decimal('15000.00')},
        {'dias': 5, 'hora_inicio': time(16, 30), 'duracion_min': 90, 'cupo': 8, 'precio': Decimal('15000.00')},
        {'dias': 7, 'hora_inicio': time(11, 0), 'duracion_min': 90, 'cupo': 4, 'precio': Decimal('15000.00')},
    ],
    'Física Mecánica': [
        {'dias': 3, 'hora_inicio': time(11, 30), 'duracion_min': 90, 'cupo': 6, 'precio': Decimal('18000.00')},
        {'dias': 5, 'hora_inicio': time(10, 0), 'duracion_min': 90, 'cupo': 5, 'precio': Decimal('18000.00')},
        {'dias': 6, 'hora_inicio': time(15, 0), 'duracion_min': 90, 'cupo': 4, 'precio': Decimal('18000.00')},
        {'dias': 8, 'hora_inicio': time(10, 0), 'duracion_min': 90, 'cupo': 8, 'precio': Decimal('18000.00')},
    ],
    'Programación en Python': [
        {'dias': 4, 'hora_inicio': time(18, 0), 'duracion_min': 90, 'cupo': 10, 'precio': Decimal('20000.00')},
        {'dias': 5, 'hora_inicio': time(19, 30), 'duracion_min': 90, 'cupo': 8, 'precio': Decimal('20000.00')},
        {'dias': 6, 'hora_inicio': time(18, 0), 'duracion_min': 90, 'cupo': 7, 'precio': Decimal('20000.00')},
        {'dias': 8, 'hora_inicio': time(11, 30), 'duracion_min': 90, 'cupo': 10, 'precio': Decimal('20000.00')},
    ],
    'Inglés Avanzado': [
        {'dias': 3, 'hora_inicio': time(16, 0), 'duracion_min': 90, 'cupo': 6, 'precio': Decimal('16000.00')},
        {'dias': 4, 'hora_inicio': time(10, 0), 'duracion_min': 90, 'cupo': 5, 'precio': Decimal('16000.00')},
        {'dias': 6, 'hora_inicio': time(16, 0), 'duracion_min': 90, 'cupo': 6, 'precio': Decimal('16000.00')},
        {'dias': 7, 'hora_inicio': time(17, 0), 'duracion_min': 90, 'cupo': 8, 'precio': Decimal('16000.00')},
    ],
}


class Command(BaseCommand):
    help = 'Genera de 3 a 4 sesiones en diferentes horarios para cada clase disponible.'

    @transaction.atomic
    def handle(self, *args, **options):
        clases = Clase.objects.all().select_related('asignatura', 'profesor')
        if not clases.exists():
            self.stdout.write(self.style.WARNING('No hay clases registradas. Ejecuta primero cargar_catalogos.'))
            return

        hoy = timezone.now().date()
        tz = timezone.get_current_timezone()
        total_creadas = 0

        for clase in clases:
            nombre_asig = clase.asignatura.nombre
            plantillas = SESIONES_POR_ASIGNATURA.get(nombre_asig)

            # Fallback genérico si es una asignatura no configurada en el diccionario
            if not plantillas:
                plantillas = [
                    {'dias': 3, 'hora_inicio': time(10, 0), 'duracion_min': 90, 'cupo': 6, 'precio': Decimal('15000.00')},
                    {'dias': 4, 'hora_inicio': time(15, 0), 'duracion_min': 90, 'cupo': 5, 'precio': Decimal('15000.00')},
                    {'dias': 6, 'hora_inicio': time(17, 0), 'duracion_min': 90, 'cupo': 8, 'precio': Decimal('15000.00')},
                    {'dias': 7, 'hora_inicio': time(11, 30), 'duracion_min': 90, 'cupo': 4, 'precio': Decimal('15000.00')},
                ]

            creadas_clase = 0
            for item in plantillas:
                fecha = hoy + timedelta(days=item['dias'])
                dt_inicio = timezone.make_aware(datetime.combine(fecha, item['hora_inicio']), tz)
                dt_fin = dt_inicio + timedelta(minutes=item['duracion_min'])

                _, creado = SesionClase.objects.get_or_create(
                    clase=clase,
                    fecha_hora_inicio=dt_inicio,
                    defaults={
                        'fecha_hora_fin': dt_fin,
                        'cupo_maximo': item['cupo'],
                        'precio': item['precio'],
                        'estado': SesionClase.ESTADO_PROGRAMADA,
                    }
                )
                if creado:
                    creadas_clase += 1

            total_creadas += creadas_clase
            self.stdout.write(f'{clase}: {creadas_clase} nuevas sesiones generadas.')

        self.stdout.write(self.style.SUCCESS(f'Proceso completado: {total_creadas} sesiones creadas en total.'))
