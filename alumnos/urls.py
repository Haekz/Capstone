#from django.conf.urls import url
from django.urls import path
from .views import (
    home, contactos, nosotros, planes, servicios, simulador, opcion_user,
    regis_alum, alumnos_reg, alumno_pag1, custom_login, logout_alumno,
    enviar_reporte, inscribir_clase, cancelar_inscripcion
)

urlpatterns = [
    path('', home, name='home'),
    path('contactos', contactos, name='contactos'),
    path('nosotros', nosotros, name='nosotros'),
    path('planes', planes, name='planes'),
    path('servicios', servicios, name='servicios'),
    path('simulador', simulador, name='simulador'),
    path('select', opcion_user, name='opcion_user'),
    path('registro_alumno', regis_alum, name='regis_alum'),
    path('alumnos_reg', alumnos_reg, name='alumnos_reg'),
    path('alumno_home', alumno_pag1, name='alumno_pag1'),
    path('login/', custom_login, name='custom_login_alumno'),
    path('logout_alumno/', logout_alumno, name='logout_alumno'),
    path('enviar_reporte/', enviar_reporte, name='enviar_reporte'),
    path('inscribir_clase/', inscribir_clase, name='inscribir_clase'),
    path('cancelar_inscripcion/<int:pk>/', cancelar_inscripcion, name='cancelar_inscripcion'),
]

