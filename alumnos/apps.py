from django.apps import AppConfig
from django.core.management import call_command
from django.db.models.signals import post_migrate


def crear_tabla_cache(using, **kwargs):
    """Tabla de la cache compartida del limite de intentos (S4-02). Omite la que ya existe."""
    call_command('createcachetable', database=using, verbosity=0)


class AlumnosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'alumnos'

    def ready(self):
        # Con cada migrate (local, Railway y pruebas) y sin una migracion que choque con otras ramas.
        post_migrate.connect(crear_tabla_cache, sender=self)
