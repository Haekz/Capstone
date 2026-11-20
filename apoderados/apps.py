from django.apps import AppConfig


class ApoderadosConfig(AppConfig):
    name = 'apoderados'
    verbose_name = 'Apoderados'

    def ready(self):
        from . import checks  # registra los chequeos de check --deploy
