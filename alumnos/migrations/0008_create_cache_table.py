from django.db import migrations
from django.core.management import call_command


def crear_tabla_cache(apps, schema_editor):
    try:
        call_command('createcachetable', 'lbwus_cache_table', verbosity=0)
    except Exception:
        pass


def revertir_tabla_cache(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0007_pago_inscripcion_pago'),
    ]

    operations = [
        migrations.RunPython(crear_tabla_cache, revertir_tabla_cache),
    ]
