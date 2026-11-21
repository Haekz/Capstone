from django import forms
from alumnos.models import Alumno, Genero
from alumnos.utils import CORREO_YA_REGISTRADO, correo_en_uso, normalizar_telefono, rut_en_uso, validar_clave_nueva
from django.contrib.auth import get_user_model

from .models import MensajeContacto

User = get_user_model()


class MensajeContactoForm(forms.ModelForm):
    """Formulario publico de contacto. La pagina lo dibuja a mano; aqui solo se valida.
    Los mensajes son los mismos que muestra la pagina: el servidor y el navegador dicen lo mismo."""

    class Meta:
        model = MensajeContacto
        fields = ['nombre', 'correo', 'mensaje']
        error_messages = {
            'nombre': {'required': 'Por favor, dinos tu nombre.',
                       'max_length': 'Tu nombre puede tener hasta %(limit_value)d caracteres.'},
            'correo': {'required': 'Por favor, ingresa un correo válido.',
                       'invalid': 'Por favor, ingresa un correo válido.'},
            'mensaje': {'required': 'Por favor, escribe tu mensaje.',
                        'max_length': 'Tu mensaje puede tener hasta %(limit_value)d caracteres.'},
        }


class AjustesAdminForm(forms.Form):
    """Los datos del propio admin (Ajustes del dashboard). El RUT no esta: es la identidad de la cuenta y el registro
    de supresiones guarda su huella, asi que se muestra de solo lectura. Telefono y direccion son opcionales porque
    crear_admin no los pide. Lo dibuja a mano includes/dashboard/perfil.html."""

    nombre = forms.CharField(label='Nombre', max_length=150)
    correo = forms.EmailField(label='Correo electrónico', max_length=254)
    telefono = forms.CharField(label='Teléfono', max_length=20, required=False)
    direccion = forms.CharField(label='Dirección', max_length=100, required=False)

    CAMPOS_DEL_USUARIO = {'nombre': 'first_name', 'correo': 'email', 'telefono': 'telefono', 'direccion': 'direccion'}

    def __init__(self, *args, user, **kwargs):
        self.user = user
        kwargs.setdefault('auto_id', 'ajustes-%s')  # el dashboard tiene otros formularios: ids propios
        kwargs.setdefault('initial', {campo: getattr(user, atributo) for campo, atributo in self.CAMPOS_DEL_USUARIO.items()})
        super().__init__(*args, **kwargs)

    def clean_correo(self):
        correo = self.cleaned_data['correo']
        if correo_en_uso(correo, excluir_user=self.user):
            raise forms.ValidationError(CORREO_YA_REGISTRADO)
        return correo

    def clean_telefono(self):
        telefono = normalizar_telefono(self.cleaned_data['telefono'])
        if telefono is None:
            raise forms.ValidationError('Ingresa un teléfono chileno de 9 dígitos, por ejemplo 912345678 o +56 9 1234 5678.')
        return telefono

    def save(self):
        for campo, atributo in self.CAMPOS_DEL_USUARIO.items():
            setattr(self.user, atributo, self.cleaned_data[campo])
        self.user.save(update_fields=list(self.CAMPOS_DEL_USUARIO.values()))
        return self.user


class AdminAlumnoForm(forms.ModelForm):
    # Campos que pertenecen a CustomUser
    nombre = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre Completo'}),
        label='Nombre Completo'
    )
    rut = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'RUT (ej: 12.345.678-9)'}),
        label='RUT'
    )
    direccion = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Direcci\u00f3n'}),
        label='Direcci\u00f3n'
    )
    fecha_nacimiento = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Fecha de Nacimiento'
    )
    correo_electronico = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
        label='Correo Electr\u00f3nico'
    )
    telefono = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '987654321'}),
        label='Tel\u00e9fono',
        required=False
    )
    genero = forms.ModelChoiceField(
        queryset=Genero.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='G\u00e9nero',
        required=False
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contrase\u00f1a segura'}),
        label='Contrase\u00f1a',
        required=False
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirmar Contrase\u00f1a'}),
        label='Confirmar Contrase\u00f1a',
        required=False
    )

    class Meta:
        model = Alumno
        fields = ['nivel_educacion']
        widgets = {
            'nivel_educacion': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'nivel_educacion': 'Nivel de Educaci\u00f3n',
        }

    def __init__(self, *args, **kwargs):
        # Si estamos editando un alumno existente, precargar los datos de CustomUser
        super().__init__(*args, **kwargs)
        es_edicion = bool(self.instance and hasattr(self.instance, 'user') and self.instance.user)
        if es_edicion:
            user = self.instance.user
            self.fields['nombre'].initial = user.first_name
            self.fields['rut'].initial = user.rut
            self.fields['direccion'].initial = user.direccion
            self.fields['fecha_nacimiento'].initial = user.fecha_nacimiento
            self.fields['correo_electronico'].initial = user.email
            self.fields['telefono'].initial = user.telefono
            self.fields['genero'].initial = user.genero
            self.fields['password'].required = False
            self.fields['password'].help_text = 'Dejar en blanco para mantener la contrase\u00f1a actual.'
            self.fields['confirm_password'].required = False
        else:
            self.fields['password'].required = True
            self.fields['confirm_password'].required = True

    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data.get('fecha_nacimiento')
        if fecha:
            from alumnos.utils import error_fecha_nacimiento
            error = error_fecha_nacimiento(fecha)
            if error:
                raise forms.ValidationError(error)
        return fecha

    def clean_rut(self):
        rut = self.cleaned_data.get('rut')
        if rut:
            from alumnos.utils import validar_rut_chileno
            if not validar_rut_chileno(rut):
                raise forms.ValidationError('El RUT ingresado no es v\u00e1lido.')

            # Otro usuario con este RUT, escrito en cualquier formato (antes: texto exacto, '12.345.678-5' pasaba)
            if rut_en_uso(rut, excluir_user=self._usuario_editado()):
                raise forms.ValidationError('Ya existe un usuario con este RUT.')
        return rut

    def clean_correo_electronico(self):
        correo = self.cleaned_data.get('correo_electronico')
        # Sin distinguir mayusculas, como el login (antes 'Ana@x.cl' pasaba si existia 'ana@x.cl')
        if correo_en_uso(correo, excluir_user=self._usuario_editado()):
            raise forms.ValidationError('Ya existe un usuario con este correo electr\u00f3nico.')
        return correo

    def _usuario_editado(self):
        """La cuenta del alumno que se edita (no choca consigo misma); None al crear uno nuevo."""
        return self.instance.user if self.instance and hasattr(self.instance, 'user') and self.instance.user else None

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        rut = cleaned_data.get('rut')
        correo = cleaned_data.get('correo_electronico')
        es_edicion = bool(self.instance and hasattr(self.instance, 'user') and self.instance.user)

        if not es_edicion and not password:
            self.add_error('password', 'La contrase\u00f1a es obligatoria para nuevos alumnos.')

        if password:
            if password != confirm_password:
                self.add_error('confirm_password', 'Las contrase\u00f1as no coinciden.')

            # Prohibir contrase\u00f1as iguales al RUT o variaciones num\u00e9ricas/con formato
            if rut:
                rut_limpio = rut.replace('.', '').replace('-', '').strip().upper()
                pwd_limpio = password.replace('.', '').replace('-', '').strip().upper()
                if pwd_limpio == rut_limpio or password.strip() == rut.strip():
                    self.add_error('password', 'Por seguridad, la contrase\u00f1a no puede ser igual al RUT.')

            # Prohibir contrase\u00f1a igual al correo
            if correo and password.strip().lower() == correo.strip().lower():
                self.add_error('password', 'Por seguridad, la contrase\u00f1a no puede ser igual al correo electr\u00f3nico.')

            # Robustez de Django contra el RUT y el correo de la cuenta (mismo helper que los registros, Seg-3)
            try:
                validar_clave_nueva(password, rut, correo)
            except forms.ValidationError as e:
                self.add_error('password', e)

        return cleaned_data

    def save(self, commit=True):
        alumno = super().save(commit=False)
        rut = self.cleaned_data.get('rut')
        correo = self.cleaned_data.get('correo_electronico')
        nombre = self.cleaned_data.get('nombre')
        telefono = self.cleaned_data.get('telefono', '')
        direccion = self.cleaned_data.get('direccion', '')
        fecha_nacimiento = self.cleaned_data.get('fecha_nacimiento')
        genero = self.cleaned_data.get('genero')
        password = self.cleaned_data.get('password')

        if not hasattr(alumno, 'user') or not alumno.user:
            # Creando un nuevo alumno con contrase\u00f1a segura proporcionada
            user = User.objects.create_user(
                username=rut,
                rut=rut,
                email=correo,
                rol='alumno',
                password=password,
                first_name=nombre,
                telefono=telefono,
                direccion=direccion,
                fecha_nacimiento=fecha_nacimiento,
                genero=genero
            )
            alumno.user = user
        else:
            # Actualizando un alumno existente
            user = alumno.user
            user.rut = rut
            user.username = rut  # Mantener username alineado con el RUT
            user.email = correo
            user.first_name = nombre
            user.telefono = telefono
            user.direccion = direccion
            user.fecha_nacimiento = fecha_nacimiento
            user.genero = genero
            if password:
                user.set_password(password)
            if commit:
                user.save()

        if commit:
            alumno.save()
        return alumno
