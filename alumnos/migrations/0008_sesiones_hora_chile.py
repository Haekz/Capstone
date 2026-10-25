"""Las sesiones se ingresaron con TIME_ZONE='UTC': quien escribia "09:30" queria
decir 09:30 en Chile, pero se guardo 09:30 UTC. Al pasar a America/Santiago se
mostrarian 3-4 horas antes. Esta migracion conserva la hora visible: 09:30 UTC
pasa a 09:30 en Chile. Solo SesionClase (pagos e inscripciones son instantes
reales y no se tocan). Reversible.
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
        for campo in CAMPOS:
            setattr(sesion, campo, reinterpretar(getattr(sesion, campo), desde, hacia))
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
