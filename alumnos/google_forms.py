"""Formulario para terminar el registro despues de entrar con Google.

El correo NO se pide: es el que Google verifico y el que confirmo el codigo.
Tampoco se pide clave: la persona entra con Google (y si quiere una clave
para entrar con RUT, usa 'Olvidaste tu contrasena').
"""

from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Alumno, Genero, Profesor
from .utils import error_fecha_nacimiento, usuario_existe, validar_rut_chileno

ALUMNO, PROFESOR = 'alumno', 'profesor'


class CompletarRegistroGoogleForm(forms.Form):
    tipo = forms.ChoiceField(
        label='Quiero registrarme como',
        choices=[(ALUMNO, 'Alumno'), (PROFESOR, 'Profesor')],
        widget=forms.RadioSelect,
    )
    nombre = forms.CharField(label='Nombre completo', max_length=60)
    rut = forms.CharField(label='RUT', max_length=12,
                          widget=forms.TextInput(attrs={'placeholder': '12.345.678-9'}))
    telefono = forms.CharField(label='Teléfono', max_length=20,
                               widget=forms.TextInput(attrs={'placeholder': '987654321', 'type': 'tel'}))
    direccion = forms.CharField(label='Dirección', max_length=60)
    fecha_nacimiento = forms.DateField(label='Fecha de nacimiento',
                                       widget=forms.DateInput(attrs={'type': 'date'}))
    genero = forms.ModelChoiceField(label='Género', queryset=Genero.objects.all(),
                                    empty_label='Selecciona tu género')
    # Solo alumno / solo profesor: se exigen en clean() segun el tipo.
    nivel_educacion = forms.ChoiceField(
        label='Nivel de educación', required=False,
        choices=[('', 'Selecciona tu nivel')] + Alumno._meta.get_field('nivel_educacion').choices,
    )
    especialidad = forms.CharField(label='Especialidad', max_length=60, required=False,
                                   widget=forms.TextInput(attrs={'placeholder': 'Ej. Matemáticas'}))

    def __init__(self, *args, correo, user_existente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.correo = correo
        self.user_existente = user_existente

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
        tipo = datos.get('tipo')
        if tipo == ALUMNO and not datos.get('nivel_educacion'):
            self.add_error('nivel_educacion', 'Selecciona tu nivel de educación.')
        if tipo == PROFESOR and not (datos.get('especialidad') or '').strip():
            self.add_error('especialidad', 'Indica tu especialidad.')
        if datos.get('rut'):
            error = usuario_existe(datos['rut'], self.correo, excluir_user=self.user_existente)
            if error:
                raise forms.ValidationError(error)
        return datos

    @transaction.atomic
    def save(self):
        """Crea (o completa) el usuario y su perfil. Devuelve el usuario."""
        d = self.cleaned_data
        comunes = dict(nombre=d['nombre'], rut=d['rut'], direccion=d['direccion'],
                       fecha_nacimiento=d['fecha_nacimiento'], correo_electronico=self.correo,
                       telefono=d['telefono'], genero=d['genero'])

        user = self.user_existente or get_user_model()(username=d['rut'])
        user.username = d['rut']
        user.rut = d['rut']
        user.email = self.correo
        user.rol = d['tipo']
        user.first_name = d['nombre']
        user.telefono = d['telefono']
        user.direccion = d['direccion']
        user.fecha_nacimiento = d['fecha_nacimiento']
        user.genero = d['genero']
        if not user.pk:
            user.set_unusable_password()
        user.save()

        if d['tipo'] == ALUMNO:
            Alumno.objects.create(user=user, nivel_educacion=d['nivel_educacion'], **comunes)
        else:
            Profesor.objects.create(user=user, especialidad=d['especialidad'].strip(), **comunes)
        return user
