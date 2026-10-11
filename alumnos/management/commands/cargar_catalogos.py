"""python manage.py cargar_catalogos

Carga Genero, Especialidad, Asignatura y Banco con los valores de
alumnos/catalogos.py. Es idempotente: usa get_or_create y nunca borra ni
modifica registros existentes.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from alumnos import catalogos
from alumnos.models import Asignatura, Banco, Especialidad, Genero


# (etiqueta, modelo, campo, valores)
CATALOGOS = (
    ('Géneros', Genero, 'descripcion', catalogos.GENEROS),
    ('Especialidades', Especialidad, 'nombre', catalogos.ESPECIALIDADES),
    ('Asignaturas', Asignatura, 'nombre', catalogos.ASIGNATURAS),
    ('Bancos', Banco, 'nombre', catalogos.BANCOS),
)


class Command(BaseCommand):
    help = 'Carga los catálogos iniciales (géneros, especialidades, asignaturas y bancos).'

    @transaction.atomic
    def handle(self, *args, **opciones):
        for etiqueta, modelo, campo, valores in CATALOGOS:
            creados = 0
            for valor in valores:
                try:
                    _, creado = modelo.objects.get_or_create(**{campo: valor})
                except modelo.MultipleObjectsReturned:
                    # Genero.descripcion no es unico: si ya hay repetidos,
                    # el valor existe y no se toca.
                    creado = False
                creados += creado
            existentes = len(valores) - creados
            self.stdout.write(
                f'{etiqueta}: {creados} creados, {existentes} ya existían.'
            )
        self.stdout.write(self.style.SUCCESS('Catálogos listos.'))
