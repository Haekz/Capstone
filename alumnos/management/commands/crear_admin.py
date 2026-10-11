"""python manage.py crear_admin [--no-superuser]

Crea un administrador del portal: un CustomUser con su perfil Tutor (el rol
lo define el perfil, ver alumnos/roles.py). Sirve para el primer admin de una
base nueva, porque regis_tutor exige que ya haya un admin con sesion.

Los datos se piden de forma interactiva y la contrasena con getpass. La
contrasena nunca se acepta como argumento: quedaria en el historial de la
terminal y en la lista de procesos.
"""

import getpass

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import Q

from alumnos.backends import variaciones_rut
from alumnos.models import Tutor
from alumnos.utils import validar_rut_chileno


def normalizar_rut(rut):
    """'12.345.678-k' -> '12345678-K'. Supone un RUT ya validado."""
    limpio = rut.replace('.', '').replace('-', '').replace(' ', '').upper()
    return f'{limpio[:-1]}-{limpio[-1]}'


class DatosAdminForm(forms.Form):
    rut = forms.CharField(label='RUT', max_length=12)
    first_name = forms.CharField(label='Nombre', max_length=150)
    last_name = forms.CharField(label='Apellido', max_length=150)
    email = forms.EmailField(label='Correo', max_length=254)

    def clean_rut(self):
        rut = self.cleaned_data['rut']
        if not validar_rut_chileno(rut):
            raise ValidationError('El RUT ingresado no es válido.')
        rut = normalizar_rut(rut)
        # Los RUT antiguos pueden estar guardados con o sin puntos y guion.
        variantes = variaciones_rut(rut) + [rut.replace('-', '')]
        variantes += [v.lower() for v in variantes]
        existe = get_user_model().objects.filter(
            Q(rut__in=variantes) | Q(username__in=variantes)
        ).exists()
        if existe:
            raise ValidationError('Ya existe un usuario con ese RUT.')
        return rut

    def clean_email(self):
        email = self.cleaned_data['email']
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise ValidationError('Ya existe un usuario con ese correo.')
        return email


class Command(BaseCommand):
    help = 'Crea un administrador del portal (usuario y perfil Tutor).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-superuser', action='store_true',
            help='Crea el administrador del portal sin acceso a /admin/ de Django.',
        )

    def handle(self, *args, **opciones):
        try:
            datos = self._pedir_datos()
            password = self._pedir_password()
        except (EOFError, KeyboardInterrupt):
            raise CommandError('Cancelado. No se creó nada.')

        superusuario = not opciones['no_superuser']
        user = get_user_model()(
            username=datos['rut'],
            rut=datos['rut'],
            first_name=datos['first_name'],
            last_name=datos['last_name'],
            email=datos['email'],
            rol='admin',
            is_staff=superusuario,
            is_superuser=superusuario,
        )
        # Con el usuario armado, el validador de similitud compara la
        # contrasena con el RUT, el nombre y el correo.
        try:
            validate_password(password, user)
        except ValidationError as exc:
            raise CommandError(
                'Contraseña rechazada: ' + ' '.join(exc.messages)
                + ' No se creó nada.'
            )
        user.set_password(password)

        try:
            with transaction.atomic():
                user.save()
                Tutor.objects.create(user=user)
        except IntegrityError:
            raise CommandError(
                'Ya existe un usuario con ese RUT o correo. No se creó nada.'
            )

        acceso = 'con acceso a /admin/' if superusuario else 'sin acceso a /admin/'
        self.stdout.write(self.style.SUCCESS(
            f'Administrador {user.rut} creado ({acceso}). '
            'Ya puede iniciar sesión en el portal.'
        ))

    def _pedir_datos(self):
        form = DatosAdminForm()
        valores = {
            campo: input(f'{form.fields[campo].label}: ').strip()
            for campo in form.fields
        }
        form = DatosAdminForm(valores)
        if not form.is_valid():
            errores = [
                f'{form.fields[campo].label}: {mensaje}'
                for campo, mensajes in form.errors.items()
                for mensaje in mensajes
            ]
            raise CommandError(' '.join(errores) + ' No se creó nada.')
        return form.cleaned_data

    def _pedir_password(self):
        password = getpass.getpass('Contraseña: ')
        if password != getpass.getpass('Repite la contraseña: '):
            raise CommandError('Las contraseñas no coinciden. No se creó nada.')
        return password
