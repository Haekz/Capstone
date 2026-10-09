from django import forms
from alumnos.models import Alumno, Genero
from django.contrib.auth import get_user_model

User = get_user_model()

class AdminAlumnoForm(forms.ModelForm):
    # Campos que pertenecen a CustomUser
    nombre = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre Completo'}), label='Nombre Completo')
    rut = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'RUT (ej: 12.345.678-9)'}), label='RUT')
    direccion = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dirección'}), label='Dirección')
    fecha_nacimiento = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}), label='Fecha de Nacimiento')
    correo_electronico = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}), label='Correo Electrónico')
    telefono = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '987654321'}), label='Teléfono', required=False)
    genero = forms.ModelChoiceField(queryset=Genero.objects.all(), widget=forms.Select(attrs={'class': 'form-control'}), label='Género', required=False)

    class Meta:
        model = Alumno
        fields = ['nivel_educacion']
        widgets = {
            'nivel_educacion': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'nivel_educacion': 'Nivel de Educación',
        }

    def __init__(self, *args, **kwargs):
        # Si estamos editando un alumno existente, precargar los datos de CustomUser
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'user') and self.instance.user:
            user = self.instance.user
            self.fields['nombre'].initial = user.first_name
            self.fields['rut'].initial = user.rut
            self.fields['direccion'].initial = user.direccion
            self.fields['fecha_nacimiento'].initial = user.fecha_nacimiento
            self.fields['correo_electronico'].initial = user.email
            self.fields['telefono'].initial = user.telefono
            self.fields['genero'].initial = user.genero

    def clean_rut(self):
        rut = self.cleaned_data.get('rut')
        if rut:
            from alumnos.utils import validar_rut_chileno
            if not validar_rut_chileno(rut):
                raise forms.ValidationError("El RUT ingresado no es válido.")
            
            # Verificar si existe otro usuario con este RUT
            user_qs = User.objects.filter(rut=rut)
            if self.instance and hasattr(self.instance, 'user') and self.instance.user:
                user_qs = user_qs.exclude(pk=self.instance.user.pk)
            if user_qs.exists():
                raise forms.ValidationError("Ya existe un usuario con este RUT.")
        return rut
        
    def clean_correo_electronico(self):
        correo = self.cleaned_data.get('correo_electronico')
        if correo:
            user_qs = User.objects.filter(email=correo)
            if self.instance and hasattr(self.instance, 'user') and self.instance.user:
                user_qs = user_qs.exclude(pk=self.instance.user.pk)
            if user_qs.exists():
                raise forms.ValidationError("Ya existe un usuario con este correo electrónico.")
        return correo

    def save(self, commit=True):
        alumno = super().save(commit=False)
        rut = self.cleaned_data.get('rut')
        correo = self.cleaned_data.get('correo_electronico')
        nombre = self.cleaned_data.get('nombre')
        telefono = self.cleaned_data.get('telefono', '')
        direccion = self.cleaned_data.get('direccion', '')
        fecha_nacimiento = self.cleaned_data.get('fecha_nacimiento')
        genero = self.cleaned_data.get('genero')

        if not hasattr(alumno, 'user') or not alumno.user:
            # Creando un nuevo alumno
            user = User.objects.create_user(
                username=rut,
                rut=rut,
                email=correo,
                rol='alumno',
                password=rut, # Por defecto la contraseña es el RUT
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
            user.username = rut # Mantener username alineado con el RUT
            user.email = correo
            user.first_name = nombre
            user.telefono = telefono
            user.direccion = direccion
            user.fecha_nacimiento = fecha_nacimiento
            user.genero = genero
            if commit:
                user.save()
                
        if commit:
            alumno.save()
        return alumno
