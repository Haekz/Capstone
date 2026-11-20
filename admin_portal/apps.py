from django.apps import AppConfig


class AdminPortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admin_portal'

    def ready(self):
        from django.contrib.auth.signals import user_logged_in

        from . import ingresos
        user_logged_in.connect(ingresos.registrar, dispatch_uid='admin_portal_ingresos_diarios')
