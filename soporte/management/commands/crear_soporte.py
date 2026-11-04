"""python manage.py crear_soporte --categorias apoderados titulos [--lider]

Crea un agente de soporte: un CustomUser con su perfil AgenteSoporte y las
categorias de tickets que atiende. Pide los datos igual que crear_admin (la
contrasena con getpass, nunca como argumento). Sin is_staff: soporte no entra
a /admin/ de Django.
"""

from alumnos.management.commands.crear_admin import Command as CrearAdmin
from soporte.models import AgenteSoporte, Habilitacion, Ticket


class Command(CrearAdmin):
    help = 'Crea un agente de soporte (usuario, perfil y categorías que atiende).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--categorias', nargs='+', required=True, choices=[clave for clave, _ in Ticket.CATEGORIAS],
            help='Categorías de tickets que recibe.',
        )
        parser.add_argument('--lider', action='store_true', help='Líder de soporte: ve y reasigna todos los tickets.')

    def handle(self, *args, **opciones):
        def crear_perfil(user):
            agente = AgenteSoporte.objects.create(user=user, es_lider=opciones['lider'])
            Habilitacion.objects.bulk_create(
                [Habilitacion(agente=agente, categoria=categoria) for categoria in set(opciones['categorias'])]
            )

        user = self.crear_cuenta(crear_perfil, rol='soporte')
        cargo = 'Líder de soporte' if opciones['lider'] else 'Agente de soporte'
        self.stdout.write(self.style.SUCCESS(
            f'{cargo} {user.rut} creado. Ya puede iniciar sesión en el portal.'
        ))
