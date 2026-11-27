"""Fotos de perfil: del disco (MEDIA_ROOT/perfiles/) a PostgreSQL (alumnos.FotoPerfil).

Cada foto en disco se vuelve a pasar por foto.procesar: las subidas antes de que existiera siguen con su EXIF
(ubicacion GPS). Si el archivo ya no esta o no es una imagen, el profesor la vuelve a subir. Los archivos se borran
del disco solo despues del commit: si la migracion falla, no se pierde ninguna foto.
"""

import django.db.models.deletion
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import migrations, models, transaction


def foto_limpia(nombre):
    """JPEG sin metadatos de la foto guardada en disco, o None si ya no existe o no es una imagen."""
    from user_profesor import (
        foto,  # aqui y no arriba: cargar las migraciones no depende del codigo de la app
    )

    try:
        with default_storage.open(nombre, 'rb') as archivo:
            return foto.procesar(archivo)
    except (OSError, ValidationError):
        return None


def borrar_del_disco(nombres):
    for nombre in nombres:
        default_storage.delete(nombre)  # no falla si ya no estaba


def pasar_fotos_a_base(apps, schema_editor):
    CustomUser = apps.get_model('alumnos', 'CustomUser')
    FotoPerfil = apps.get_model('alumnos', 'FotoPerfil')
    con_foto = CustomUser.objects.exclude(foto_perfil='').exclude(foto_perfil=None).values_list('pk', 'foto_perfil')
    nombres = []
    for user_id, nombre in con_foto:
        jpeg = foto_limpia(nombre)
        if jpeg is not None:
            FotoPerfil.objects.create(user_id=user_id, contenido=jpeg)
        nombres.append(nombre)
    transaction.on_commit(lambda: borrar_del_disco(nombres), using=schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0044_ficha_video'),
    ]

    operations = [
        migrations.CreateModel(
            name='FotoPerfil',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='foto', serialize=False, to=settings.AUTH_USER_MODEL)),
                ('contenido', models.BinaryField()),
            ],
        ),
        # Sin vuelta atras de datos: deshacerla quita la tabla y las fotos se pierden (hay que volver a subirlas).
        migrations.RunPython(pasar_fotos_a_base, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='customuser',
            name='foto_perfil',
        ),
    ]
