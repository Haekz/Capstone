from django import forms
from alumnos.utils import CORREO_YA_REGISTRADO, correo_en_uso, normalizar_telefono

from .models import MensajeContacto


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
