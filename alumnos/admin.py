from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Genero, Tutor, Alumno, Profesor, Clase, SesionClase, Inscripcion


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
