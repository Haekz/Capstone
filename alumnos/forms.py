from django import forms
from django.contrib.auth.hashers import make_password
from .models import Alumno

class AlumnoForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña'}),
        label='Contraseña',
        min_length=6
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirmar Contraseña'}),
        label='Confirmar Contraseña',
        min_length=6
    )

    class Meta:
        model = Alumno
        fields = [
            'nombre', 'rut', 'nivel_educacion', 'direccion', 
            'fecha_nacimiento', 'correo_electronico', 'telefono', 
            'genero', 'password'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre Completo'}),
            'rut': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'RUT (ej: 12.345.678-9)'}),
            'nivel_educacion': forms.Select(attrs={'class': 'form-control'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dirección'}),
            'fecha_nacimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'correo_electronico': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '987654321'}),
            'genero': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'nombre': 'Nombre Completo',
            'rut': 'RUT',
            'nivel_educacion': 'Nivel de Educación',
            'direccion': 'Dirección',
            'fecha_nacimiento': 'Fecha de Nacimiento',
            'correo_electronico': 'Correo Electrónico',
            'telefono': 'Teléfono',
            'genero': 'Género',
            'password': 'Contraseña',
        }

    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data.get('fecha_nacimiento')
        if not fecha:
            return fecha

        from datetime import date
        today = date.today()

        if fecha == today:
            raise forms.ValidationError("No puedes elegir la fecha actual.")

        if fecha > today:
            raise forms.ValidationError("La fecha de nacimiento no puede ser una fecha futura.")

        # Calcular edad
        age = today.year - fecha.year - ((today.month, today.day) < (fecha.month, fecha.day))

        if age < 18:
            raise forms.ValidationError("Debes ser mayor o igual a 18 años.")

        return fecha

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError({"confirm_password": "Las contraseñas no coinciden."})
        return cleaned_data

    def save(self, commit=True):
        alumno = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            alumno.password = make_password(password)
        if commit:
            alumno.save()
        return alumno
