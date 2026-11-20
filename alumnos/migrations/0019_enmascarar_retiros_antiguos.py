"""Retiros antiguos con el numero de cuenta completo y sin cifrar (decidido 02-nov: enmascarar).

Antes de la cuenta bancaria cifrada (paso 3a) cada retiro guardaba el numero en claro.
Los retiros nuevos guardan una copia enmascarada ('•••• 1234', CuentaBancaria.enmascarado):
se deja la misma en los antiguos. No se puede deshacer: el numero completo no debe volver.
"""

from django.db import migrations

MASCARA = '••••'


def enmascarar(apps, schema_editor):
    SolicitudRetiro = apps.get_model('alumnos', 'SolicitudRetiro')
    for retiro in SolicitudRetiro.objects.exclude(numero_cuenta='').exclude(numero_cuenta__startswith=MASCARA):
        numero = retiro.numero_cuenta.replace(' ', '').replace('-', '')  # como CuentaBancaria.asignar_numero
        retiro.numero_cuenta = f'{MASCARA} {numero[-4:]}'
        retiro.save(update_fields=['numero_cuenta'])


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0018_titulo_cifrado'),
    ]

    operations = [
        migrations.RunPython(enmascarar, migrations.RunPython.noop),
    ]
