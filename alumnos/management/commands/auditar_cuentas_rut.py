from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from alumnos.backends import variaciones_rut

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Audita la base de datos buscando cuentas cuyas contraseñas coincidan con su RUT "
        "o variaciones predecibles (S4-02 / S-03). Permite invalidar dichas contraseñas."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--forzar-reseteo',
            action='store_true',
            help='Invalida la contraseña de las cuentas vulnerables (set_unusable_password) para forzar recuperación.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Ejecuta la auditoría en modo simulación sin alterar datos.',
        )

    def handle(self, *args, **options):
        forzar_reseteo = options['forzar_reseteo'] and not options['dry_run']
        self.stdout.write(self.style.NOTICE("Iniciando auditoría de cuentas con contraseña basada en RUT..."))

        usuarios = User.objects.all()
        total_evaluados = 0
        total_vulnerables = 0
        total_reseteados = 0

        vulnerables = []

        for user in usuarios:
            if not user.has_usable_password():
                continue

            total_evaluados += 1
            candidatos = set()

            if user.rut:
                candidatos.update(variaciones_rut(user.rut))
                candidatos.add(user.rut.strip())
                candidatos.add(user.rut.replace('.', '').replace('-', '').strip())
                candidatos.add(user.rut.replace('.', '').replace('-', '').strip().lower())
                candidatos.add(user.rut.replace('.', '').replace('-', '').strip().upper())

            if user.username:
                candidatos.add(user.username.strip())
                candidatos.update(variaciones_rut(user.username))

            es_vulnerable = False
            for cand in candidatos:
                if cand and user.check_password(cand):
                    es_vulnerable = True
                    break

            if es_vulnerable:
                total_vulnerables += 1
                accion = "Detectado"
                if forzar_reseteo:
                    user.set_unusable_password()
                    user.save(update_fields=['password'])
                    total_reseteados += 1
                    accion = "Contraseña invalidada (Reset forzado)"

                vulnerables.append({
                    'id': user.id,
                    'username': user.username,
                    'rut': user.rut or 'N/A',
                    'email': user.email or 'N/A',
                    'rol': user.rol,
                    'accion': accion,
                })

        # Mostrar reporte
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("REPORTE DE AUDITORÍA DE SEGURIDAD (S-03)")
        self.stdout.write("=" * 70)
        self.stdout.write(f"Total de usuarios con contraseña activa: {total_evaluados}")
        self.stdout.write(f"Cuentas vulnerables detectadas: {total_vulnerables}")
        self.stdout.write(f"Cuentas con reseteo forzado aplicado: {total_reseteados}")
        self.stdout.write("-" * 70)

        if vulnerables:
            for item in vulnerables:
                self.stdout.write(
                    f"- [ID {item['id']}] {item['username']} ({item['rol']}) "
                    f"RUT: {item['rut']} | Email: {item['email']} -> {item['accion']}"
                )
        else:
            self.stdout.write(self.style.SUCCESS("No se encontraron cuentas vulnerables con contraseña igual al RUT."))

        self.stdout.write("=" * 70 + "\n")
        return f"Auditoría finalizada. {total_vulnerables} vulnerables encontrados."
