from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, Genero, Tutor, Alumno, Profesor, Clase, SesionClase,
    Inscripcion, PlanAlumno, DesgloseOperacion, PaqueteClases, Suscripcion,
)


# Aseguramiento de acceso a /admin/ (S4-02):
# Restringido estrictamente a personal administrativo con is_staff activo.
def admin_site_has_permission(request):
    return bool(
        request.user
        and request.user.is_authenticated
        and request.user.is_active
        and request.user.is_staff
    )

admin.site.has_permission = admin_site_has_permission

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


class PlanAlumnoAdmin(admin.ModelAdmin):
    list_display = ['id_plan_alumno', 'alumno', 'tipo_plan', 'total_clases', 'clases_disponibles', 'clases_consumidas', 'monto_total', 'estado', 'created_at']
    list_filter = ['tipo_plan', 'estado', 'created_at']
    search_fields = ['alumno__user__first_name', 'alumno__user__last_name', 'alumno__user__email']


admin.site.register(PlanAlumno, PlanAlumnoAdmin)


class DesgloseOperacionAdmin(admin.ModelAdmin):
    list_display = ['id_desglose', 'tipo_operacion', 'monto_bruto', 'comision_lbwus', 'monto_tutor', 'estado', 'alumno', 'profesor', 'fecha_operacion']
    list_filter = ['tipo_operacion', 'estado', 'fecha_operacion']
    search_fields = ['alumno__user__first_name', 'alumno__user__last_name', 'profesor__user__first_name', 'profesor__user__last_name']
    readonly_fields = ['fecha_operacion']


admin.site.register(DesgloseOperacion, DesgloseOperacionAdmin)

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
