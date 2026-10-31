"""Las sesiones se ingresaron con TIME_ZONE='UTC': quien escribia "09:30" queria
decir 09:30 en Chile, pero se guardo 09:30 UTC. Al pasar a America/Santiago se
mostrarian 3-4 horas antes. Esta migracion conserva la hora visible: 09:30 UTC
pasa a 09:30 en Chile. Solo SesionClase (pagos e inscripciones son instantes
reales y no se tocan). Reversible, salvo una sesion que empiece en la hora que no
existe en Chile (00:00-00:59 la noche del cambio de hora de septiembre).
"""
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.db import migrations

UTC = dt_timezone.utc
CHILE = ZoneInfo('America/Santiago')
CAMPOS = ('fecha_hora_inicio', 'fecha_hora_fin')


def reinterpretar(fecha, desde, hacia):
    """Misma hora de reloj, otra zona: 09:30 en `desde` -> 09:30 en `hacia`."""
    return fecha.astimezone(desde).replace(tzinfo=hacia)


def _mover(apps, desde, hacia):
    SesionClase = apps.get_model('alumnos', 'SesionClase')
    sesiones = list(SesionClase.objects.only('pk', *CAMPOS))
    for sesion in sesiones:
        # Se mueve el inicio y se conserva la duracion. Mover inicio y fin por
        # separado fallaba en la noche del cambio de hora: 00:30-01:30 de
        # septiembre quedaba con inicio == fin, violaba sesion_fin_posterior_a_inicio
        # y abortaba toda la migracion. Se suma en UTC: sumar a una hora con zona
        # de Chile suma en hora de reloj y repetiria el problema.
        duracion = sesion.fecha_hora_fin - sesion.fecha_hora_inicio
        sesion.fecha_hora_inicio = reinterpretar(sesion.fecha_hora_inicio, desde, hacia).astimezone(UTC)
        sesion.fecha_hora_fin = sesion.fecha_hora_inicio + duracion
    SesionClase.objects.bulk_update(sesiones, CAMPOS, batch_size=500)


def a_hora_chile(apps, schema_editor):
    _mover(apps, UTC, CHILE)


def a_utc(apps, schema_editor):
    _mover(apps, CHILE, UTC)


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0007_suscripcion'),
    ]

    operations = [
        migrations.RunPython(a_hora_chile, a_utc),
    ]
