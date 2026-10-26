from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Genero, Tutor, Alumno, Profesor, Clase, SesionClase, Inscripcion, PaqueteClases, Suscripcion

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
admin.site.register(SesionClase)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ['id_inscripcion', 'alumno', 'clase', 'sesion', 'estado', 'fecha_inscripcion']
    list_filter = ['estado', 'fecha_inscripcion', 'clase__asignatura']
    search_fields = ['alumno__user__first_name', 'alumno__user__last_name', 'clase__asignatura__nombre']

admin.site.register(Inscripcion, InscripcionAdmin)


# Soporte de pagos: buscar por buy_order de Webpay ("pagué y no tengo plan").
class SuscripcionAdmin(admin.ModelAdmin):
    list_display = ['buy_order', 'alumno', 'plan', 'monto', 'estado', 'creada', 'fecha_fin']
    list_filter = ['estado', 'plan']
    search_fields = ['buy_order', 'alumno__user__first_name', 'alumno__user__last_name']

admin.site.register(Suscripcion, SuscripcionAdmin)


# Mismo soporte para los paquetes de clases ("pagué y no puedo reservar").
class PaqueteClasesAdmin(admin.ModelAdmin):
    list_display = ['buy_order', 'alumno', 'profesor', 'plan', 'clases', 'monto', 'estado', 'creada', 'fecha_fin']
    list_filter = ['estado', 'plan']
    search_fields = ['buy_order', 'alumno__user__first_name', 'alumno__user__last_name']

admin.site.register(PaqueteClases, PaqueteClasesAdmin)