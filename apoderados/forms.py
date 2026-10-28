from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

from alumnos.utils import error_fecha_nacimiento, usuario_existe, validar_rut_chileno

from .models import Apoderado, RevisionIdentidad

# Al cambiar el texto, subir la version: cada apoderado guarda la que acepto.
# Texto provisorio, sujeto a la revision juridica (decision 15).
VERSION_DECLARACION = '1'
DECLARACION = (
    'Declaro que soy mayor de edad, que los datos que entrego son verdaderos y que solo '
    'solicitaré vincular a estudiantes respecto de quienes tengo la representación legal o el '
    'cuidado personal. Entiendo que LBWUS revisará mi identidad antes de habilitar la cuenta, y '
    'que una cuenta verificada no da, por sí sola, permisos sobre ningún estudiante.'
)


class RegistroApoderadoForm(forms.Form):
    nombre = forms.CharField(label='Nombre completo', max_length=60)
    rut = forms.CharField(label='RUT', max_length=12,
                          widget=forms.TextInput(attrs={'placeholder': '12.345.678-9'}))
    correo = forms.EmailField(label='Correo electrónico')
    telefono = forms.CharField(label='Teléfono (opcional)', max_length=20, required=False,
                               widget=forms.TextInput(attrs={'type': 'tel'}))
    fecha_nacimiento = forms.DateField(label='Fecha de nacimiento',
                                       widget=forms.DateInput(attrs={'type': 'date'}))
    password = forms.CharField(label='Contraseña', widget=forms.PasswordInput,
                               strip=False)
    confirmar_password = forms.CharField(label='Repite la contraseña', widget=forms.PasswordInput,
                                         strip=False)
    acepta_declaracion = forms.BooleanField(label=DECLARACION)

    def full_clean(self):
        super().full_clean()
        # Accesibilidad: el lector de pantalla anuncia el error junto a su campo.
        for nombre in self.errors:
            if nombre in self.fields:
                self.fields[nombre].widget.attrs['aria-describedby'] = f'{self[nombre].auto_id}-error'

    def clean_rut(self):
        rut = self.cleaned_data['rut'].strip()
        if not validar_rut_chileno(rut):
            raise forms.ValidationError('El RUT ingresado no es válido.')
        return rut

    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data['fecha_nacimiento']
        error = error_fecha_nacimiento(fecha)
        if error:
            raise forms.ValidationError(error)
        return fecha

    def clean(self):
        datos = super().clean()
        rut, correo, password = datos.get('rut'), datos.get('correo'), datos.get('password')
        if rut and correo:
            error = usuario_existe(rut, correo)
            if error:
                raise forms.ValidationError(error)
        if password:
            if password != datos.get('confirmar_password'):
                self.add_error('confirmar_password', 'Las contraseñas no coinciden.')
            User = get_user_model()
            try:
                validate_password(password, User(username=rut or '', email=correo or '',
                                                 first_name=datos.get('nombre', '')))
            except forms.ValidationError as error:
                self.add_error('password', error)
        return datos

    def save(self):
        datos = self.cleaned_data
        with transaction.atomic():
            user = get_user_model().objects.create_user(
                username=datos['rut'], rut=datos['rut'], email=datos['correo'], rol='apoderado',
                password=datos['password'], first_name=datos['nombre'],
                telefono=datos['telefono'], fecha_nacimiento=datos['fecha_nacimiento'],
            )
            return Apoderado.objects.create(user=user, version_declaracion=VERSION_DECLARACION,
                                            declaracion_aceptada=timezone.now())


class RevisionIdentidadForm(forms.ModelForm):
    class Meta:
        model = RevisionIdentidad
        fields = ['decision', 'documento', 'canal', 'rut_coincide', 'observacion']

    def clean(self):
        datos = super().clean()
        if datos.get('decision') == RevisionIdentidad.APROBAR:
            if not datos.get('documento') or not datos.get('canal'):
                raise forms.ValidationError('Para aprobar indica qué documento revisaste y por qué canal.')
            if not datos.get('rut_coincide'):
                raise forms.ValidationError('Solo puedes aprobar si el RUT del documento coincide.')
        elif datos.get('decision') == RevisionIdentidad.RECHAZAR and not datos.get('observacion'):
            raise forms.ValidationError('Para rechazar escribe el motivo: el apoderado lo verá.')
        return datos
