"""Lo que ya estaba por revisar al desplegar queda como ticket sin asignar.

Sin esto, los apoderados, vinculos y titulos pendientes desaparecerian de golpe:
el administrador ya no los ve y soporte solo ve tickets. Quedan sin asignar
porque al migrar aun no hay agentes; el lider los asigna.
Un vinculo solo se revisa con la identidad del apoderado verificada.
"""

from django.db import migrations


def abrir_tickets_pendientes(apps, schema_editor):
    Ticket = apps.get_model('soporte', 'Ticket')
    Apoderado = apps.get_model('apoderados', 'Apoderado')
    Vinculo = apps.get_model('apoderados', 'Vinculo')
    Profesor = apps.get_model('alumnos', 'Profesor')
    Ticket.objects.bulk_create(
        [Ticket(categoria='apoderados', apoderado=a)
         for a in Apoderado.objects.filter(estado='revision_pendiente')]
        + [Ticket(categoria='apoderados', vinculo=v)
           for v in Vinculo.objects.filter(estado='pendiente', apoderado__estado='verificado')]
        + [Ticket(categoria='titulos', profesor=p)
           for p in Profesor.objects.filter(titulo_estado='en_revision')]
    )


class Migration(migrations.Migration):

    dependencies = [
        ('soporte', '0001_equipo_y_tickets'),
        ('apoderados', '0006_documentos_por_revisar'),
        ('alumnos', '0012_rol_soporte'),
    ]

    operations = [
        migrations.RunPython(abrir_tickets_pendientes, migrations.RunPython.noop),
    ]
