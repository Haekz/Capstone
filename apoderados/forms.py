from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

from alumnos.models import Alumno
from alumnos.utils import (EDAD_ADULTA, EDAD_MINIMA_ESTUDIANTE, edad, error_fecha_nacimiento,
                           usuario_existe, validar_rut_chileno)

from .models import Apoderado, Revision, RevisionIdentidad, RevisionVinculo, Vinculo

# Al cambiar un texto, subir su version: cada registro guarda la que se acepto.
# Textos provisorios, sujetos a la revision juridica (decision 15).
VERSION_DECLARACION = '1'
DECLARACION = (
    'Declaro que soy mayor de edad, que los datos que entrego son verdaderos y que solo '
    'solicitaré vincular a estudiantes respecto de quienes tengo la representación legal o el '
    'cuidado personal. Entiendo que LBWUS revisará mi identidad antes de habilitar la cuenta, y '
    'que una cuenta verificada no da, por sí sola, permisos sobre ningún estudiante.'
)
VERSION_DECLARACION_VINCULO = '1'
DECLARACION_VINCULO = (
    'Declaro que soy la madre o el padre de este estudiante, que sus datos son verdaderos y que '
    'mostraré su certificado de nacimiento para que LBWUS verifique el vínculo. Entiendo que, '
    'mientras tanto, la cuenta del estudiante no podrá reservar, comprar ni entrar a clases.'
)


class AccesibleMixin:
    def full_clean(self):
        super().full_clean()
        # El lector de pantalla anuncia el error junto a su campo.
        for nombre in self.errors:
            if nombre in self.fields:
                self.fields[nombre].widget.attrs['aria-describedby'] = f'{self[nombre].auto_id}-error'


class _CuentaForm(AccesibleMixin, forms.Form):
    """Datos comunes para crear una cuenta: nombre, RUT y contrasena."""
    nombre = forms.CharField(label='Nombre completo', max_length=60)
    rut = forms.CharField(label='RUT', max_length=12,
                          widget=forms.TextInput(attrs={'placeholder': '12.345.678-9'}))
    password = forms.CharField(label='Contraseña', widget=forms.PasswordInput, strip=False)
    confirmar_password = forms.CharField(label='Repite la contraseña', widget=forms.PasswordInput,
                                         strip=False)

    def clean_rut(self):
        rut = self.cleaned_data['rut'].strip()
        if not validar_rut_chileno(rut):
            raise forms.ValidationError('El RUT ingresado no es válido.')
        return rut

    def clean(self):
        datos = super().clean()
        rut, correo, password = datos.get('rut'), datos.get('correo'), datos.get('password')
        if rut:
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


class RegistroApoderadoForm(_CuentaForm):
    correo = forms.EmailField(label='Correo electrónico')
    telefono = forms.CharField(label='Teléfono (opcional)', max_length=20, required=False,
                               widget=forms.TextInput(attrs={'type': 'tel'}))
    fecha_nacimiento = forms.DateField(label='Fecha de nacimiento',
                                       widget=forms.DateInput(attrs={'type': 'date'}))
    acepta_declaracion = forms.BooleanField(label=DECLARACION)

    field_order = ['nombre', 'rut', 'correo', 'telefono', 'fecha_nacimiento',
                   'password', 'confirmar_password', 'acepta_declaracion']

    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data['fecha_nacimiento']
        error = error_fecha_nacimiento(fecha)
        if error:
            raise forms.ValidationError(error)
        return fecha

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


class RegistroEstudianteForm(_CuentaForm):
    """El apoderado crea la cuenta del menor: entra con su RUT y la contrasena que se define aqui."""
    fecha_nacimiento = forms.DateField(label='Fecha de nacimiento del estudiante',
                                       widget=forms.DateInput(attrs={'type': 'date'}))
    nivel_educacion = forms.ChoiceField(label='Nivel de educación',
                                        choices=Alumno._meta.get_field('nivel_educacion').choices)
    parentesco = forms.ChoiceField(label='Tu parentesco con el estudiante', choices=Vinculo.PARENTESCOS)
    correo = forms.EmailField(label='Correo del estudiante (opcional)', required=False)
    acepta_declaracion = forms.BooleanField(label=DECLARACION_VINCULO)

    field_order = ['nombre', 'rut', 'fecha_nacimiento', 'nivel_educacion', 'parentesco', 'correo',
                   'password', 'confirmar_password', 'acepta_declaracion']

    def __init__(self, *args, apoderado, **kwargs):
        super().__init__(*args, **kwargs)
        self.apoderado = apoderado

    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data['fecha_nacimiento']
        error = error_fecha_nacimiento(fecha, edad_minima=EDAD_MINIMA_ESTUDIANTE)
        if not error and edad(fecha) >= EDAD_ADULTA:
            error = 'Si el estudiante tiene 18 años o más, debe crear su propia cuenta.'
        if error:
            raise forms.ValidationError(error)
        return fecha

    def save(self):
        datos = self.cleaned_data
        with transaction.atomic():
            user = get_user_model().objects.create_user(
                username=datos['rut'], rut=datos['rut'], email=datos['correo'], rol='alumno',
                password=datos['password'], first_name=datos['nombre'],
                fecha_nacimiento=datos['fecha_nacimiento'],
            )
            alumno = Alumno.objects.create(user=user, nivel_educacion=datos['nivel_educacion'])
            return Vinculo.objects.create(
                apoderado=self.apoderado, alumno=alumno, parentesco=datos['parentesco'],
                version_declaracion=VERSION_DECLARACION_VINCULO, declaracion_aceptada=timezone.now(),
            )


class ClaveEstudianteForm(AccesibleMixin, SetPasswordForm):
    """El apoderado define una contrasena nueva para el estudiante a su cargo."""


class _RevisionForm(forms.ModelForm):
    def clean(self):
        datos = super().clean()
        if datos.get('decision') == Revision.APROBAR:
            self.validar_aprobacion(datos)
        elif datos.get('decision') == Revision.RECHAZAR and not datos.get('observacion'):
            raise forms.ValidationError('Para rechazar escribe el motivo: el apoderado lo verá.')
        return datos

    def validar_aprobacion(self, datos):
        raise NotImplementedError


class RevisionIdentidadForm(_RevisionForm):
    class Meta:
        model = RevisionIdentidad
        fields = ['decision', 'documento', 'canal', 'rut_coincide', 'observacion']

    def validar_aprobacion(self, datos):
        if not datos.get('documento') or not datos.get('canal'):
            raise forms.ValidationError('Para aprobar indica qué documento revisaste y por qué canal.')
        if not datos.get('rut_coincide'):
            raise forms.ValidationError('Solo puedes aprobar si el RUT del documento coincide.')


class RevisionVinculoForm(_RevisionForm):
    class Meta:
        model = RevisionVinculo
        fields = ['decision', 'canal', 'certificado_coincide', 'observacion']

    def validar_aprobacion(self, datos):
        if not datos.get('canal'):
            raise forms.ValidationError('Para aprobar indica por qué canal revisaste el certificado.')
        if not datos.get('certificado_coincide'):
            raise forms.ValidationError('Solo puedes aprobar si el certificado de nacimiento confirma el parentesco.')
