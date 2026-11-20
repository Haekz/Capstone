"""Plazo de cada ticket: los que ya existian lo cuentan desde que se abrieron.

Se agrega nullable, se calcula y recien ahi pasa a obligatorio: ningun ticket
queda sin plazo. Usa soporte.plazos (funcion pura, sin modelos).
"""

from django.db import migrations, models

from soporte.plazos import vencimiento

DIAS_HABILES = {'apoderados': 5, 'titulos': 5}


def calcular_vencimientos(apps, schema_editor):
    Ticket = apps.get_model('soporte', 'Ticket')
    for ticket in Ticket.objects.all():
        ticket.vence = vencimiento(ticket.creado, DIAS_HABILES[ticket.categoria])
        ticket.save(update_fields=['vence'])


class Migration(migrations.Migration):

    dependencies = [
        ('soporte', '0002_tickets_de_pendientes'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='vence',
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(calcular_vencimientos, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='ticket',
            name='vence',
            field=models.DateTimeField(),
        ),
    ]
