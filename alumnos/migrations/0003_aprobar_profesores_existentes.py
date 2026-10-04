"""Los profesores que ya existian antes del requisito quedan aprobados.

Sin esto, al desplegar todos pasarian a 'pendiente' y desaparecerian de
golpe para los alumnos. El requisito aplica a los profesores NUEVOS. Si se
quiere exigir el titulo tambien a los antiguos, basta con no correr esta
migracion (o pasarlos a 'pendiente' desde el admin).
"""

from django.db import migrations


def aprobar_existentes(apps, schema_editor):
    Profesor = apps.get_model('alumnos', 'Profesor')
    Profesor.objects.filter(titulo_estado='pendiente').update(
        titulo_estado='aprobado',
        titulo_observacion='Profesor registrado antes del requisito de título.',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0002_titulo_profesor'),
    ]

    operations = [
        migrations.RunPython(aprobar_existentes, migrations.RunPython.noop),
    ]
