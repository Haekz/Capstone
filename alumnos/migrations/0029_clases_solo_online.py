# Todas las clases son online: la modalidad presencial no existe (decidido 07-nov).
# Las clases que estuvieran como presencial pasan a online; no se borra ninguna (arrastraria reservas).

from django.db import migrations, models


def presenciales_a_online(apps, schema_editor):
    apps.get_model('alumnos', 'Clase').objects.filter(modalidad='presencial').update(modalidad='online')


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0028_especializacion_otra_asignatura'),
    ]

    operations = [
        migrations.RunPython(presenciales_a_online, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='clase',
            name='modalidad',
            field=models.CharField(choices=[('online', 'Online')], max_length=10),
        ),
    ]
