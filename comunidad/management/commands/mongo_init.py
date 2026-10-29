"""python manage.py mongo_init [--verificar] [--si]

Hace ping, aplica los validadores $jsonSchema y crea los indices de las
colecciones de comunidad/esquemas.py. Es idempotente.
"""

from django.core.management.base import BaseCommand, CommandError
from pymongo.errors import PyMongoError

from comunidad import esquemas, mongo


class Command(BaseCommand):
    help = 'Inicializa las colecciones de MongoDB (validadores e índices).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verificar', action='store_true',
            help='Solo hace ping e informa la base y la latencia.',
        )
        parser.add_argument(
            '--si', action='store_true',
            help='No pide confirmación aunque la base termine en _prod.',
        )

    def handle(self, *args, **opciones):
        base = mongo.nombre_db()
        try:
            latencia = mongo.ping()
        except mongo.MongoNoConfigurado:
            raise CommandError(
                'MongoDB no está configurado: define la variable MONGODB_URI.'
            )
        except PyMongoError as exc:
            # Solo el nombre de la excepcion: el mensaje puede incluir el host.
            raise CommandError(
                f'MongoDB no responde ({type(exc).__name__}). '
                'Revisa la red, la IP permitida en Atlas y las credenciales.'
            )

        self.stdout.write(f'Base: {base} · latencia: {latencia} ms')
        if opciones['verificar']:
            return

        if base.endswith('_prod') and not opciones['si']:
            respuesta = input(
                f'Vas a modificar la base de PRODUCCIÓN "{base}". '
                'Escribe "si" para continuar: '
            )
            if respuesta.strip().lower() != 'si':
                raise CommandError('Cancelado: no se modificó nada.')

        db = mongo.get_db()
        try:
            validadores = esquemas.aplicar_validadores(db)
            indices = esquemas.crear_indices(db)
        except PyMongoError as exc:
            raise CommandError(
                f'Error al inicializar MongoDB ({type(exc).__name__}).'
            )

        self.stdout.write(f'{"Colección":<16}{"Validador":<13}Índices')
        for nombre in esquemas.COLECCIONES:
            self.stdout.write(
                f'{nombre:<16}{validadores[nombre]:<13}'
                f'{", ".join(indices[nombre])}'
            )
        self.stdout.write(self.style.SUCCESS('MongoDB inicializado.'))
