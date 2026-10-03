from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Genero, Tutor, Alumno, Profesor, Clase, Inscripcion

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'rut', 'email', 'rol', 'is_staff', 'is_active']
    fieldsets = UserAdmin.fieldsets + (
        ('Información de Perfil', {'fields': ('rol', 'rut', 'telefono', 'direccion', 'fecha_nacimiento', 'genero')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información de Perfil', {'fields': ('rol', 'rut', 'telefono', 'direccion', 'fecha_nacimiento', 'genero')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Genero)
admin.site.register(Tutor)
admin.site.register(Alumno)
admin.site.register(Profesor)
admin.site.register(Clase)
admin.site.register(Inscripcion)