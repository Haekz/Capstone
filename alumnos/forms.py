from django import forms
from .models import Alumno

class AlumnoForm(forms.ModelForm):
    class Meta:
        model = Alumno
        fields = [
            'nombre', 'rut', 'nivel_educacion', 'direccion', 
            'fecha_nacimiento', 'correo_electronico', 'telefono', 
            'genero', 'id_tutor'
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
            
        }
